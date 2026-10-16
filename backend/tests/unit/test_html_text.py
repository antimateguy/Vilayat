"""Reading the text of an official page."""

from jobs.html_text import page_text

FILLER = "The residence permit is issued for the duration of the studies. " * 4


def page(body: str) -> str:
    return (
        f"<html><head><title>x</title><script>var a = 1;</script></head><body>{body}</body></html>"
    )


def test_the_main_content_is_kept_and_the_page_furniture_left_out() -> None:
    html = page(
        "<header>Skip to content</header><nav><a>Home</a></nav>"
        f"<main><h1>Title</h1><h2>Requirements</h2><p>{FILLER}</p>"
        "<ul><li>Passport</li><li>Proof of admission</li></ul></main>"
        "<footer>Imprint</footer>"
    )

    text = page_text(html)

    assert text.startswith("## Requirements")
    assert "- Passport\n- Proof of admission" in text
    assert "Skip to content" not in text and "Imprint" not in text and "var a" not in text


def test_an_article_wins_over_main_so_readers_comments_stay_out() -> None:
    html = page(
        f"<main><article><h2>Minijobs</h2><p>{FILLER}</p></article>"
        '<div id="comments"><p>I have a question about my own case, please answer.</p></div></main>'
    )

    assert "my own case" not in page_text(html)


def test_a_site_specific_container_and_furniture_sections() -> None:
    html = page(
        '<div id="layout-grid__area--maincontent">'
        f"<h2>Fees</h2><p>{FILLER}</p><p>Vorlesen</p><p>10 EUR</p>"
        "<h2>Download</h2><p>Seite als PDF herunterladen, bitte hier klicken.</p></div>"
        '<div role="dialog"><p>Search the whole site for anything at all today.</p></div>'
    )

    text = page_text(html)

    assert "## Fees" in text and "10 EUR" in text
    assert "Vorlesen" not in text and "Download" not in text and "whole site" not in text


def test_a_page_without_enough_text_gives_nothing() -> None:
    assert page_text(page("<main><p>Too short.</p></main>")) == ""


def test_links_and_emphasis_stay_inside_their_sentence() -> None:
    html = page(
        "<main><p>In a shared flat <strong>one fee per flat</strong> is due, see "
        f'<a href="/x">the rules</a>. {FILLER}</p></main>'
    )

    assert "In a shared flat one fee per flat is due, see the rules." in page_text(html)


def test_a_skipped_section_takes_its_sub_headings_with_it() -> None:
    html = page(
        f"<main><h2>Fee</h2><p>{FILLER}</p><h2>Ähnliche Themen</h2>"
        "<h3>Recall of baby food</h3><p>An unrelated article teaser that is long enough.</p>"
        f"<h2>Moving out</h2><p>{FILLER}</p></main>"
    )

    text = page_text(html)

    assert "baby food" not in text and "unrelated" not in text
    assert "## Moving out" in text
