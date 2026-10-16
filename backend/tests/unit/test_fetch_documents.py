"""The fetch job's rules, with the network replaced by prepared replies."""

import json
from datetime import date
from pathlib import Path

import pytest

from jobs.fetch_documents import (
    SOURCES_FILE,
    USER_AGENT,
    Fetcher,
    FetchRefusedError,
    Response,
    Source,
    decode,
    read_sources,
    reserves_mining,
    run,
)
from jobs.ingest_documents import read_document

ALLOWED = frozenset({"example.org"})
TEXT = "Students may work 140 full days or 280 half days a year. " * 5
PAGE = f"<html><body><main><h2>Work</h2><p>{TEXT}</p></main></body></html>".encode()
SOURCE = Source(
    "work-rules", "Working while studying", "https://example.org/work", None, False, "X"
)


class Site:
    """Prepared replies by address; records what was asked for."""

    def __init__(self, pages: dict[str, Response | Exception]) -> None:
        self.pages = pages
        self.asked: list[str] = []

    def __call__(self, url: str) -> Response:
        self.asked.append(url)
        reply = self.pages.get(url, FetchRefusedError("HTTP 404"))
        if isinstance(reply, Exception):
            raise reply
        return reply


def ok(url: str, body: bytes = PAGE, headers: dict[str, str] | None = None) -> Response:
    return Response(url, headers or {"Content-Type": "text/html; charset=utf-8"}, body)


def robots(rules: str) -> Response:
    return Response("https://example.org/robots.txt", {}, rules.encode())


def test_the_allow_list_in_the_repository_is_valid() -> None:
    sources, _ = read_sources(json.loads(SOURCES_FILE.read_text(encoding="utf-8")))

    assert sources and all(source.url.startswith("https://") for source in sources)
    # Only the laws, which carry no copyright, may be quoted word for word.
    quotable = {source.key for source in sources if source.can_quote}
    assert all(key.startswith("law-") for key in quotable)


def test_a_source_off_the_allowed_domains_is_refused() -> None:
    data = {
        "allowed_domains": ["example.org"],
        "sources": [{"key": "x", "title": "X", "url": "https://elsewhere.org/", "publisher": "X"}],
    }
    with pytest.raises(ValueError, match="allow-list"):
        read_sources(data)


def test_a_page_is_fetched_when_robots_allow_it() -> None:
    site = Site(
        {
            "https://example.org/robots.txt": robots("User-agent: *\nDisallow: /private/"),
            "https://example.org/work": ok("https://example.org/work"),
        }
    )

    text = Fetcher(ALLOWED, site).text_of(SOURCE)

    assert text.startswith("## Work") and "140 full days" in text


@pytest.mark.parametrize(
    ("pages", "reason"),
    [
        ({"https://example.org/robots.txt": robots("User-agent: *\nDisallow: /")}, "robots"),
        # robots.txt that cannot be read is not taken as permission.
        ({"https://example.org/robots.txt": FetchRefusedError("HTTP 500")}, "robots"),
        (
            {
                "https://example.org/robots.txt": robots(""),
                "https://example.org/work": ok("https://elsewhere.org/work"),
            },
            "off the allow-list",
        ),
        (
            {
                "https://example.org/robots.txt": robots(""),
                "https://example.org/work": ok(
                    "https://example.org/work", headers={"tdm-reservation": "1"}
                ),
            },
            "text and data mining",
        ),
        (
            {
                "https://example.org/robots.txt": robots(""),
                "https://example.org/work": ok("https://example.org/work", b"<main>Hi</main>"),
            },
            "no readable text",
        ),
    ],
    ids=["disallowed", "robots unreadable", "redirected away", "mining reserved", "empty"],
)
def test_a_page_is_refused(pages: dict[str, Response | Exception], reason: str) -> None:
    site = Site(pages)

    with pytest.raises(FetchRefusedError, match=reason):
        Fetcher(ALLOWED, site).text_of(SOURCE)

    if reason == "robots":
        assert site.asked == ["https://example.org/robots.txt"]


def test_mining_reservations_in_the_page_are_found() -> None:
    assert reserves_mining({}, '<meta name="tdm-reservation" content="1">')
    assert reserves_mining({}, '<meta name="robots" content="noindex, noai">')
    assert reserves_mining({"X-Robots-Tag": "noai"}, "")
    assert not reserves_mining({}, '<meta name="robots" content="index, follow">')


def test_the_declared_character_set_is_used() -> None:
    body = "Gesetz über den Aufenthalt".encode("iso-8859-1")

    assert decode(Response("u", {"Content-Type": "text/html; charset=iso-8859-1"}, body)) == (
        "Gesetz über den Aufenthalt"
    )
    in_page = b'<meta charset="iso-8859-1">' + body
    assert decode(Response("u", {}, in_page)).endswith("Gesetz über den Aufenthalt")


def test_a_run_writes_documents_the_ingestion_job_can_read(tmp_path: Path) -> None:
    site = Site(
        {
            "https://example.org/robots.txt": robots(""),
            "https://example.org/work": ok("https://example.org/work"),
        }
    )
    missing = Source("missing", "Gone", "https://example.org/gone", "berlin", True, "X")
    pauses: list[None] = []

    problems = run(
        [SOURCE, missing],
        Fetcher(ALLOWED, site),
        tmp_path,
        date(2026, 10, 16),
        lambda: pauses.append(None),
    )
    document = read_document(tmp_path / "work-rules.md")

    assert problems == {"missing": "HTTP 404"}
    assert len(pauses) == 1
    assert (document.title, document.source_url) == ("Working while studying", SOURCE.url)
    assert (document.is_sample, document.can_quote) == (False, False)
    assert document.retrieved_on == date(2026, 10, 16)
    assert "User-Agent" not in USER_AGENT and "Vilayat" in USER_AGENT
