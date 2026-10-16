"""Fetch the Ask library's official pages from the allow-list, offline.

    uv run python -m jobs.fetch_documents
    uv run python -m jobs.ingest_documents

Reads data/documents/sources.json and, for each page on it, writes
data/documents/fetched/<key>.md with the page's text and a header naming the
source and the day it was read. jobs.ingest_documents then cuts and embeds the
files like any other document. Nothing is fetched while a student waits.

Rules this job keeps:
- only pages on the allow-list, and only on its allowed domains (redirects
  included);
- the program names itself in the User-Agent header and follows robots.txt;
- a page that reserves text and data mining (a "tdm-reservation" header or
  meta tag, or "noai" in its robots directives) is skipped (section 44b UrhG);
- one request every two seconds at most;
- the fetched text is not committed to Git (see .gitignore); it is stored only
  to be searched. Unless its source says can_quote, the app shows an answer
  and a link, never the passage itself.
"""

import json
import logging
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from jobs.html_text import page_text
from jobs.runtime import configure_logging, https_context

logger = logging.getLogger("jobs.fetch_documents")

DOCUMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "documents"
SOURCES_FILE = DOCUMENTS_DIR / "sources.json"
FETCHED_DIR = DOCUMENTS_DIR / "fetched"
USER_AGENT = "Vilayat-document-fetcher/0.1 (student project; reads each page once, offline)"
PAUSE_SECONDS = 2.0
TIMEOUT_SECONDS = 30
MIN_TEXT = 200


@dataclass(frozen=True)
class Source:
    key: str
    title: str
    url: str
    city: str | None
    can_quote: bool
    publisher: str


@dataclass(frozen=True)
class Response:
    url: str
    """The address after redirects."""
    headers: Mapping[str, str]
    body: bytes


type Fetch = Callable[[str], Response]


class FetchRefusedError(Exception):
    """The page was not fetched or not kept; the message says why."""


def read_sources(data: Mapping[str, object]) -> tuple[list[Source], frozenset[str]]:
    allowed = frozenset(str(domain) for domain in data["allowed_domains"])  # type: ignore[attr-defined]
    sources = []
    keys: set[str] = set()
    for entry in data["sources"]:  # type: ignore[attr-defined]
        source = Source(
            key=entry["key"],
            title=entry["title"],
            url=entry["url"],
            city=entry.get("city"),
            can_quote=bool(entry.get("can_quote", False)),
            publisher=entry["publisher"],
        )
        if not re.fullmatch(r"[a-z0-9-]+", source.key) or source.key in keys:
            raise ValueError(f"source key {source.key!r} must be unique, lowercase and hyphenated")
        if urlsplit(source.url).scheme != "https" or urlsplit(source.url).hostname not in allowed:
            raise ValueError(
                f"{source.key}: {source.url} is not an https address on the allow-list"
            )
        keys.add(source.key)
        sources.append(source)
    return sources, allowed


def http_fetch(url: str) -> Response:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT_SECONDS, context=https_context()
        ) as reply:
            return Response(reply.geturl(), dict(reply.headers.items()), reply.read())
    except urllib.error.HTTPError as error:
        raise FetchRefusedError(f"HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise FetchRefusedError(f"could not connect: {error}") from error


def reserves_mining(headers: Mapping[str, str], html: str) -> bool:
    """True when the publisher has opted out of text and data mining."""
    lowered = {key.lower(): value.lower() for key, value in headers.items()}
    if lowered.get("tdm-reservation", "").strip() == "1":
        return True
    if "noai" in lowered.get("x-robots-tag", ""):
        return True
    for name, content in re.findall(
        r'<meta[^>]+name=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']', html, re.I
    ):
        if name.lower() == "tdm-reservation" and content.strip() == "1":
            return True
        if name.lower() == "robots" and "noai" in content.lower():
            return True
    return False


def decode(response: Response) -> str:
    """The page as text, in the character set it declares (UTF-8 if none)."""
    charset = "utf-8"
    in_header = re.search(r"charset=([\w-]+)", response.headers.get("Content-Type", ""), re.I)
    in_page = re.search(rb"charset=[\"']?([\w-]+)", response.body[:2048], re.I)
    if in_header:
        charset = in_header.group(1)
    elif in_page:
        charset = in_page.group(1).decode("ascii")
    try:
        return response.body.decode(charset, errors="replace")
    except LookupError:
        return response.body.decode("utf-8", errors="replace")


def document_file(source: Source, text: str, retrieved_on: date) -> str:
    header = [
        "---",
        f"title: {source.title}",
        f"source_url: {source.url}",
        f"retrieved_on: {retrieved_on.isoformat()}",
        f"city: {source.city or ''}",
        "is_sample: false",
        f"can_quote: {'true' if source.can_quote else 'false'}",
        "---",
    ]
    return "\n".join(header) + "\n" + text.strip() + "\n"


class Fetcher:
    def __init__(self, allowed: frozenset[str], fetch: Fetch = http_fetch) -> None:
        self._allowed = allowed
        self._fetch = fetch
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def text_of(self, source: Source) -> str:
        if not self._may_fetch(source.url):
            raise FetchRefusedError("robots.txt does not allow it")
        response = self._fetch(source.url)
        if urlsplit(response.url).hostname not in self._allowed:
            raise FetchRefusedError(f"redirected off the allow-list, to {response.url}")
        html = decode(response)
        if reserves_mining(response.headers, html):
            raise FetchRefusedError("the publisher reserves text and data mining")
        text = page_text(html)
        if len(text) < MIN_TEXT:
            raise FetchRefusedError("no readable text found on the page")
        return text

    def _may_fetch(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            robots = urllib.robotparser.RobotFileParser()
            try:
                robots.parse(decode(self._fetch(f"{host}/robots.txt")).splitlines())
            except FetchRefusedError:
                # No robots.txt is permission; an error reading it is not.
                robots.parse(["User-agent: *", "Disallow: /"])
            self._robots[host] = robots
        return self._robots[host].can_fetch(USER_AGENT, url)


def run(
    sources: list[Source],
    fetcher: Fetcher,
    directory: Path,
    retrieved_on: date,
    pause: Callable[[], None] = lambda: time.sleep(PAUSE_SECONDS),
) -> dict[str, str]:
    """Fetch every source; returns the problem for each one that failed. A page
    that fails keeps the file of its last good fetch, if there is one."""
    directory.mkdir(parents=True, exist_ok=True)
    problems: dict[str, str] = {}
    for number, source in enumerate(sources):
        if number:
            pause()
        try:
            text = fetcher.text_of(source)
        except FetchRefusedError as error:
            problems[source.key] = str(error)
            logger.warning("%s: not fetched: %s", source.key, error)
            continue
        (directory / f"{source.key}.md").write_text(
            document_file(source, text, retrieved_on), encoding="utf-8", newline="\n"
        )
        logger.info("%s: %d characters", source.key, len(text))
    return problems


def main() -> int:
    configure_logging()
    sources, allowed = read_sources(json.loads(SOURCES_FILE.read_text(encoding="utf-8")))
    problems = run(sources, Fetcher(allowed), FETCHED_DIR, date.today())
    logger.info("%d of %d pages fetched", len(sources) - len(problems), len(sources))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
