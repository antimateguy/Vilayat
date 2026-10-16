"""The two charts of the evaluation, drawn from the saved results.

    uv run --group eval python -m evaluation.charts

Redraws docs/evaluation/*.png from results.json without calling any model. The
notebook uses the same functions, so a chart in the report always matches the
figures in results.json.

One look for both charts: a quiet surface, ink for text, colour only for data.
The two colours were checked for colour-vision-deficiency separation and for
contrast against the surface.
"""

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from evaluation.report import RESULTS_DIR

SURFACE, INK, INK_2, HAIRLINE = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
BLUE, ORANGE = "#2a78d6", "#eb6834"
# Typed loosely: the library types its settings as a fixed list of key names.
STYLE: Any = {
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "xtick.color": INK_2,
    "ytick.color": INK,
    "axes.edgecolor": HAIRLINE,
    "font.size": 10,
}


def retrieval_chart(results: dict[str, Any]) -> Figure:
    """Mean reciprocal rank per embedding model, best at the top."""
    ordered = sorted(results["retrieval"].items(), key=lambda item: item[1]["mrr"])
    questions = results["material"]["answerable_questions"]
    with plt.rc_context(STYLE):
        figure, axis = plt.subplots(figsize=(7, 2.6))
        bars = axis.barh(
            [name for name, _ in ordered],
            [row["mrr"] for _, row in ordered],
            height=0.5,
            color=BLUE,
        )
        axis.bar_label(bars, fmt="%.2f", padding=4, color=INK)
        axis.set_xlim(0, 1.08)
        axis.set_xticks([0, 0.25, 0.5, 0.75, 1])
        axis.grid(axis="x", color=HAIRLINE, linewidth=1)
        _quiet(axis)
        axis.set_xlabel("Mean reciprocal rank (1 = the right section is always ranked first)")
        axis.set_title(
            f"Retrieval quality by embedding model, {questions} questions",
            loc="left",
            fontsize=11,
            fontweight="bold",
        )
        figure.tight_layout()
    return figure


def similarity_chart(results: dict[str, Any]) -> Figure:
    """Each question's best similarity, in two rows, with the app's threshold."""
    gate = results["similarity_gate"]
    threshold = gate["at_app_threshold"]["threshold"]
    groups = [
        ("The documents answer it", gate["answerable_best"], BLUE, 1.0),
        ("The documents do not", gate["unanswerable_best"], ORANGE, 0.0),
    ]
    with plt.rc_context(STYLE):
        figure, axis = plt.subplots(figsize=(7, 3.0))
        for label, values, colour, row in groups:
            axis.scatter(
                values,
                [row + offset for offset in _spread(len(values))],
                s=60,
                color=colour,
                # A ring in the surface colour keeps overlapping dots apart.
                edgecolor=SURFACE,
                linewidth=1.5,
                label=f"{label} ({len(values)})",
            )
        axis.axvline(threshold, color=INK_2, linewidth=1)
        axis.text(
            threshold - 0.004,
            1.42,
            f"threshold {threshold:.2f}",
            ha="right",
            va="center",
            color=INK_2,
        )
        axis.set_yticks([1.0, 0.0], ["Answerable", "Not answerable"])
        axis.set_ylim(-0.45, 1.6)
        axis.grid(axis="x", color=HAIRLINE, linewidth=1)
        _quiet(axis)
        axis.set_xlabel(f"Similarity of the best-matching section ({gate['model']})")
        axis.set_title("Best similarity per question", loc="left", fontsize=11, fontweight="bold")
        axis.legend(
            loc="upper left",
            bbox_to_anchor=(0, -0.32),
            ncol=2,
            frameon=False,
            fontsize=9,
            borderaxespad=0,
            handletextpad=0.3,
        )
        figure.tight_layout()
    return figure


def save_charts(results: dict[str, Any], directory: Path) -> list[Path]:
    saved = []
    for name, draw in (("retrieval", retrieval_chart), ("similarity_gate", similarity_chart)):
        figure = draw(results)
        path = directory / f"{name}.png"
        figure.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(figure)
        saved.append(path)
    return saved


def _quiet(axis: Axes) -> None:
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.tick_params(length=0)
    axis.set_axisbelow(True)


def _spread(count: int) -> list[float]:
    """Small fixed vertical offsets, so that dots with similar values stay apart."""
    return [((index * 7) % 11 - 5) * 0.035 for index in range(count)]


def main() -> int:
    source = RESULTS_DIR / "results.json"
    if not source.exists():
        print(f"{source} not found: run notebooks/evaluation.ipynb first", file=sys.stderr)
        return 1
    for path in save_charts(json.loads(source.read_text(encoding="utf-8")), RESULTS_DIR):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
