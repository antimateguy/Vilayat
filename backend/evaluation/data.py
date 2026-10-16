"""The labelled questions and sentences the evaluation runs on.

Both files were written for this project. They are small and were not
collected from students, so the results show whether the pipeline works, not
how it would score on real traffic.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EVALUATION_DIR = Path(__file__).resolve().parents[1] / "data" / "evaluation"

ChunkId = tuple[str, str]
"""(document key, section heading): one searchable passage."""


@dataclass(frozen=True, slots=True)
class Question:
    text: str
    city: str
    relevant: frozenset[ChunkId] = frozenset()
    """The sections that answer the question. Empty for an unanswerable one."""
    language: str = "en"


@dataclass(frozen=True, slots=True)
class ExpectedIntent:
    """What a sentence should set. None or empty means: left alone."""

    city: str | None = None
    campus: tuple[str, str] | None = None
    """(university short name, campus name)."""
    employer: str | None = None
    max_rent_eur: int | None = None
    max_commute_minutes: int | None = None
    important: tuple[str, ...] = ()
    unimportant: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LabelledSentence:
    text: str
    current_city: str
    expected: ExpectedIntent = field(default_factory=ExpectedIntent)


def load_questions(directory: Path = EVALUATION_DIR) -> tuple[list[Question], list[Question]]:
    """(answerable, unanswerable) questions."""
    raw = _read(directory / "retrieval_questions.json")
    answerable = [
        Question(
            item["question"],
            item["city"],
            frozenset((document, section) for document, section in item["relevant"]),
            item.get("language", "en"),
        )
        for item in raw["answerable"]
    ]
    unanswerable = [Question(item["question"], item["city"]) for item in raw["unanswerable"]]
    return answerable, unanswerable


def load_sentences(directory: Path = EVALUATION_DIR) -> list[LabelledSentence]:
    raw = _read(directory / "intent_sentences.json")
    sentences = []
    for item in raw["sentences"]:
        expected = dict(item["expected"])
        campus = expected.pop("campus", None)
        sentences.append(
            LabelledSentence(
                text=item["sentence"],
                current_city=item["current_city"],
                expected=ExpectedIntent(
                    campus=(campus[0], campus[1]) if campus else None,
                    important=tuple(expected.pop("important", ())),
                    unimportant=tuple(expected.pop("unimportant", ())),
                    **expected,
                ),
            )
        )
    return sentences


def _read(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded
