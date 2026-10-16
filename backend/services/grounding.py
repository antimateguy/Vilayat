"""Checking that text written by the model sticks to the figures it was given.

The model is asked to reword, never to compute or recall. A figure in its text
that is not in its input is therefore a sign of invention, and the text is
rejected. The same goes for a name: in plain English only names are written
with a capital letter inside a sentence, so a capitalised word that is not in
the input is a place the model made up or misspelt.

This catches invented amounts, days, dates and places. It cannot catch an
invented claim that contains neither; the prompts and the labels in the app
cover that part.
"""

import re
from collections.abc import Iterable

# 1,500 and 11,904: a comma followed by exactly three digits groups thousands.
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    """Every figure written in digits, in one spelling: "1,500" becomes "1500"
    and "18.360" becomes "18.36"."""
    return {_canonical(match) for match in _NUMBER.findall(_THOUSANDS.sub("", text))}


def unsupported_numbers(text: str, sources: Iterable[str]) -> set[str]:
    """Figures in the text that appear in none of the sources."""
    allowed: set[str] = set()
    for source in sources:
        allowed |= numbers_in(source)
    return numbers_in(text) - allowed


def _canonical(number: str) -> str:
    return number.rstrip("0").rstrip(".") if "." in number else number


_WORD = re.compile(r"[^\W\d_][\w-]*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_POSSESSIVE = re.compile(r"['\u2019]s\b")


def unsupported_names(text: str, sources: Iterable[str], allowed: Iterable[str] = ()) -> set[str]:
    """Capitalised words inside a sentence that appear in none of the sources.

    The first word of a sentence is skipped, because it is capitalised anyway.
    `allowed` lists capitalised words that are fine without a source, such as "EUR".
    """
    known = set(allowed)
    for source in sources:
        known.update(_WORD.findall(source))
    unsupported: set[str] = set()
    for sentence in _SENTENCE_END.split(_POSSESSIVE.sub("", text)):
        for word in _WORD.findall(sentence)[1:]:
            if word[0].isupper() and word not in known:
                unsupported.add(word)
    return unsupported
