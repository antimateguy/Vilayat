"""The readable text of an official web page, as Markdown sections.

Only the standard library's HTML parser is used. A page is read once; every
piece of text remembers which candidate containers it sits in (the page's
<main>, an <article>, and a few site-specific content boxes), and the most
specific container that holds a real amount of text wins. Navigation, headers,
footers, forms, scripts and pop-up dialogs are skipped.
"""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

# Most specific first. A container is used when it holds at least MIN_TEXT characters.
CONTAINERS = (
    "#layout-grid__area--maincontent",  # service.berlin.de
    ".jnhtml",  # gesetze-im-internet.de: the text of one section
    "article",  # before <main>: on blogs, readers' comments sit outside the article
    "main",
    "body",
)
MIN_TEXT = 200
SKIPPED = {
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "button",
    "svg",
    "template",
    "select",
}
# Inside a sentence: their text joins the sentence instead of breaking it.
INLINE = {
    "a",
    "abbr",
    "b",
    "cite",
    "code",
    "dfn",
    "em",
    "i",
    "kbd",
    "label",
    "mark",
    "q",
    "s",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "time",
    "u",
}
VOID = {"br", "img", "input", "meta", "link", "hr", "area", "base", "col", "source", "wbr"}
HEADINGS = {"h2": 2, "h3": 3, "h4": 3}
# Page furniture that comes as its own section: dropped with what follows it.
STOP_HEADINGS = {
    "download",
    "verwandte dienstleistungen",
    "bürgertelefon 115",
    "für sie zuständig",
    "das könnte sie auch interessieren",
    "kommentare",
    "teilen",
    "links und downloads",
    "kontakt",
    "ähnliche themen",
    "artikel zum thema",
    "beratung & angebote",
    "wählen sie ihr bundesland",
    "aktuelles",
    "internet",
    "telefon",
    "post",
    "adresse",
    "anfahrt",
    "weiterführende informationen",
}
STOP_HEADING_STARTS = ("bekanntmachung",)
"""Notices about outages and the like, which date quickly."""
SHORTEST_PARAGRAPH = 25
"""Shorter lines without a figure are buttons and labels ("Vorlesen")."""
NOISE = ("personenbezogene Daten (IP-Adresse", "Alle Artikel zum Thema")
DATE_LINE = re.compile(r"(Stand:\s*)?\d{1,2}\.\s*\w+\.?\s+\d{4}")
"""A paragraph that is only a date, as under article teasers ("1. Okt. 2026")."""


@dataclass
class _Open:
    tag: str
    containers: frozenset[str]
    skipped: bool
    buffer: list[str] = field(default_factory=list)


def _matches(tag: str, attributes: dict[str, str]) -> set[str]:
    classes = set(attributes.get("class", "").split())
    element_id = attributes.get("id", "")
    found = set()
    for selector in CONTAINERS:
        if (
            (selector.startswith("#") and element_id == selector[1:])
            or (selector.startswith(".") and selector[1:] in classes)
            or selector == tag
        ):
            found.add(selector)
    return found


def _is_skipped(tag: str, attributes: dict[str, str]) -> bool:
    classes = attributes.get("class", "")
    names = f"{classes} {attributes.get('id', '')}".lower()
    return (
        # Readers' comments under an article are not the publisher's text.
        "comment" in names
        or "wpdiscuz" in names
        or tag in SKIPPED
        or attributes.get("role") in ("dialog", "navigation", "banner", "contentinfo")
        or "robots-nocontent" in classes
        or attributes.get("aria-hidden") == "true"
        or "hidden" in attributes
    )


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[_Open] = [_Open("#root", frozenset(), False)]
        # (containers, kind, text): kind is "h2", "h3", "li" or "p".
        self.blocks: list[tuple[frozenset[str], str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        parent = self.stack[-1]
        if tag in VOID:
            if tag == "br":
                parent.buffer.append("\n")
            return
        if tag not in INLINE:
            self._flush(parent)
        self.stack.append(
            _Open(
                tag,
                parent.containers | _matches(tag, attributes),
                parent.skipped or _is_skipped(tag, attributes),
            )
        )

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID or all(item.tag != tag for item in self.stack[1:]):
            return
        while self.stack[-1].tag != tag:
            self._close(self.stack.pop())
        self._close(self.stack.pop())

    def handle_data(self, data: str) -> None:
        self.stack[-1].buffer.append(data)

    def close(self) -> None:
        super().close()
        while len(self.stack) > 1:
            self._close(self.stack.pop())

    def _close(self, item: _Open) -> None:
        if item.tag in INLINE:
            # Hand the text back to the sentence it belongs to.
            if not item.skipped:
                self.stack[-1].buffer.append("".join(item.buffer))
            return
        self._flush(item)

    def _flush(self, item: _Open) -> None:
        text = _tidy("".join(item.buffer))
        item.buffer.clear()
        if not text or item.skipped:
            return
        if item.tag in HEADINGS:
            kind = f"h{HEADINGS[item.tag]}"
        elif item.tag == "li":
            kind = "li"
        else:
            kind = "p"
        self.blocks.append((item.containers, kind, text))


def _tidy(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def page_text(html: str) -> str:
    """Markdown: "## " headings, "- " list items and paragraphs. Empty if the
    page has no readable text."""
    reader = _Reader()
    reader.feed(html)
    reader.close()
    for container in CONTAINERS:
        blocks = [(kind, text) for found, kind, text in reader.blocks if container in found]
        if sum(len(text) for _, text in blocks) >= MIN_TEXT:
            return _markdown(blocks)
    return ""


def _markdown(blocks: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    # The level of the furniture heading being skipped: everything under it,
    # sub-headings included, goes until a heading of the same level or higher.
    skipping: int | None = None
    for kind, text in blocks:
        if kind in ("h2", "h3"):
            level = int(kind[1])
            heading = text.strip().lower()
            if skipping is not None and level > skipping:
                continue
            furniture = heading in STOP_HEADINGS or heading.startswith(STOP_HEADING_STARTS)
            skipping = level if furniture else None
        if skipping is not None or any(marker in text for marker in NOISE):
            continue
        if kind == "p" and len(text) < SHORTEST_PARAGRAPH and not re.search(r"\d", text):
            continue
        # A teaser for another article stops mid-sentence: "Wir geben einen Überblick..."
        if kind == "p" and text.rstrip().endswith(("...", "…")):
            continue
        if kind == "p" and DATE_LINE.fullmatch(text.strip()):
            continue
        if kind in ("h2", "h3"):
            lines += ["", f"## {text}", ""]
        elif kind == "li":
            lines.append(f"- {text}")
        else:
            lines += [text, ""]
    return _without_empty_sections(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip())


def _without_empty_sections(markdown: str) -> str:
    """Drop headings with nothing under them before the next heading."""
    lines = markdown.split("\n")
    kept: list[str] = []
    for number, line in enumerate(lines):
        if line.startswith("## "):
            rest = lines[number + 1 :]
            following = next((item for item in rest if item.strip()), "")
            if not following or following.startswith("## "):
                continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
