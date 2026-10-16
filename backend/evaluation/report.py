"""Write docs/evaluation/README.md from the results the notebook saved.

    uv run python -m evaluation.report

The summary is generated from results.json, so its figures cannot drift from
what was measured. Run it after the notebook.
"""

import json
import sys
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "evaluation"


def percent(value: float) -> str:
    return f"{round(100 * value)}%"


def render(results: dict[str, Any]) -> str:
    material = results["material"]
    retrieval = sorted(results["retrieval"].items(), key=lambda item: -item[1]["mrr"])
    german = results["retrieval_german_only"]
    gate = results["similarity_gate"]
    used = gate["at_app_threshold"]
    answers = results["answers"]
    yes, no = answers["answerable"], answers["unanswerable"]
    intent = results["intent"]

    lines = [
        "# Evaluation of the AI layer",
        "",
        f"Measured on {results['run_on']} by `backend/notebooks/evaluation.ipynb`. "
        "This page is generated from `results.json` by `python -m evaluation.report`; "
        "do not edit it by hand.",
        "",
        f"- Text model: `{results['text_model']}`",
        f"- Embedding model in the app: `{results['embedding_model_in_app']}`",
        f"- Material: {material['documents']} sample documents cut into "
        f"{material['sections']} sections, {material['answerable_questions']} questions they "
        f"answer, {material['unanswerable_questions']} they do not, and "
        f"{material['sentences']} sentences.",
        "",
        "The questions, sentences and labels were written for this project and are few. "
        "The figures show that the pipeline works and how the models compare on this "
        "material. They do not predict results on real questions from students.",
        "",
        "## 1. Retrieval by embedding model",
        "",
        "For each question the document sections are ranked by similarity. Hit@1 is the "
        "share of questions whose top section is one that answers them; MRR rewards "
        "ranking the right section high (1 is perfect).",
        "",
        "| Model | Hit@1 | Hit@3 | MRR | "
        f"Top section right, {german['questions']} German questions |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| `{name}` | {percent(row['hit_at_1'])} | {percent(row['hit_at_3'])} | "
        f"{row['mrr']:.2f} | {round(german[name] * german['questions'])} of {german['questions']} |"
        for name, row in retrieval
    ]
    lines += [
        "",
        "![Mean reciprocal rank by embedding model](retrieval.png)",
        "",
        "## 2. The similarity threshold",
        "",
        f"With `{gate['model']}`, the best-matching section of an answerable question had a "
        f"similarity between {gate['answerable_min']:.2f} and {gate['answerable_max']:.2f}. "
        f"For a question the documents do not answer it was between "
        f"{gate['unanswerable_min']:.2f} and {gate['unanswerable_max']:.2f}.",
        "",
        f"At the threshold the app uses ({used['threshold']:.2f}), "
        f"{percent(used['answerable_kept'])} of the answerable questions pass and "
        f"{percent(used['unanswerable_stopped'])} of the unanswerable ones are stopped "
        "before any model is called. The rest of the unanswerable ones reach the text "
        "model, which can still decline (see part 3).",
        "",
        "| Threshold | Answerable kept | Unanswerable stopped | Both decided correctly |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {row['threshold']:.2f} | {percent(row['answerable_kept'])} | "
        f"{percent(row['unanswerable_stopped'])} | {percent(row['accuracy'])} |"
        for row in gate["by_threshold"]
    ]
    lines += [
        "",
        "![Best similarity per question](similarity_gate.png)",
        "",
        "## 3. Answers, end to end",
        "",
        "Every question went through the same service the API uses. An answer counts as "
        "having the right source when it cites a section labelled as answering the "
        "question. The wording of the answers was read by hand, not scored.",
        "",
        "| Outcome | Questions |",
        "| --- | --- |",
        f"| Answerable: answered, citing a right source | "
        f"{yes['answered_with_right_source']} of {yes['questions']} |",
        f"| Answerable: answered, citing only other sections | "
        f"{yes['answered_with_other_source']} |",
        f'| Answerable: refused as "no evidence" | {yes["refused_as_no_evidence"]} |',
        f"| Answerable: passages shown without an answer | {yes['passages_only']} |",
        f"| Unanswerable: correctly refused | "
        f"{no['refused_as_no_evidence']} of {no['questions']} |",
        f"| Unanswerable: answered anyway | {no['answered_anyway']} |",
        f"| Unanswerable: passages shown without an answer | {no['passages_only']} |",
        "",
        "## 4. Sentence to search settings",
        "",
        f"{intent['scored']} of {intent['sentences']} sentences were scored"
        + (
            f" ({intent['model_unavailable']} got no reply from the model)."
            if intent["model_unavailable"]
            else "."
        )
        + " A field is right when it is set to the expected value, or correctly left alone.",
        "",
        "| Field | Right |",
        "| --- | --- |",
    ]
    lines += [f"| {name} | {percent(value)} |" for name, value in intent["by_field"].items()]
    lines += [f"| **every field of a sentence** | **{percent(intent['all_fields_right'])}** |", ""]
    if intent["misses"]:
        lines += ["Sentences with a wrong field:", ""]
        lines += [
            f'- "{miss["sentence"]}": {", ".join(miss["wrong"])}' for miss in intent["misses"]
        ]
        lines.append("")
    lines += [
        "## Limits",
        "",
        "- One person wrote the system, the questions and the labels. Real questions "
        "will be messier, and these figures will be lower on them.",
        "- Part 3 checks the cited source, not the truth of every sentence.",
        "- The open models were run at default settings; larger ones were not tried.",
        "- The threshold belongs to one embedding model and must be measured again if "
        "the model changes.",
        "- A hosted model can change without notice. The date and model names are above.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    source = RESULTS_DIR / "results.json"
    if not source.exists():
        print(f"{source} not found: run notebooks/evaluation.ipynb first", file=sys.stderr)
        return 1
    results = json.loads(source.read_text(encoding="utf-8"))
    (RESULTS_DIR / "README.md").write_text(render(results), encoding="utf-8", newline="\n")
    print(f"wrote {RESULTS_DIR / 'README.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
