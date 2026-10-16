"""Per-stage timing: how long each part of handling a request took.

A service wraps a step in `with stage("ranking"):`. If something is recording
(the web layer does, once per request) the duration is noted; otherwise the
block just runs. The services stay free of any web framework.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

Stages = list[tuple[str, float]]

_recording: ContextVar[Stages | None] = ContextVar("stage_timings", default=None)


@contextmanager
def stage(name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        stages = _recording.get()
        if stages is not None:
            stages.append((name, (time.perf_counter() - start) * 1000))


@contextmanager
def recording() -> Iterator[Stages]:
    """Collect (stage name, milliseconds) for everything run inside the block."""
    stages: Stages = []
    token = _recording.set(stages)
    try:
        yield stages
    finally:
        _recording.reset(token)
