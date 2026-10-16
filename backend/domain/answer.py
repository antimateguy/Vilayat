"""Answers to questions, built from stored document passages."""

from dataclasses import dataclass
from enum import StrEnum

from domain.document import DocChunk


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    """The text is an answer and every statement in it cites a passage."""
    NO_EVIDENCE = "no_evidence"
    """The stored documents do not cover the question. Nothing was made up."""
    SOURCES_ONLY = "sources_only"
    """Relevant passages were found, but no answer that passed the checks could
    be written (the model is unavailable, or its reply was rejected)."""


@dataclass(frozen=True, slots=True)
class Citation:
    number: int
    """The number the answer text uses for this passage, as in "[2]"."""
    chunk: DocChunk
    similarity: float


@dataclass(frozen=True, slots=True)
class Answer:
    status: AnswerStatus
    text: str
    citations: tuple[Citation, ...]
    """For ANSWERED, the passages the text cites. For SOURCES_ONLY, the
    passages closest to the question. Empty for NO_EVIDENCE."""
