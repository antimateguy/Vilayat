# Labelled data for the evaluation

Used by the evaluation code in `backend/evaluation/`. Both files were written for this
project. They were not collected from students, and they are small, so the
results show that the pipeline works and how the models compare on this
material. They do not predict how the app would score on real questions.

| File | Contents |
| --- | --- |
| `retrieval_questions.json` | 38 questions the sample documents answer, each with the document section or sections that answer it, and 14 questions they do not answer. Two of the answerable questions are in German (`"language": "de"`). |
| `intent_sentences.json` | 30 sentences a student might type, each with the search settings it should produce. Four are meant to produce nothing or to drop a value (a wish no setting can hold, a rent in dollars, a university that is not in the catalogue). Two are in German. |

A section is named by the document's file name without `.md` and its `## `
heading. `tests/unit/test_evaluation.py` checks that every label points at a
section that exists and belongs to the question's city, so a change to the
documents cannot silently break the labels.

In `intent_sentences.json` the expected values use names, not database ids. A
university named without a campus is expected to give its main campus. A field
that is absent means the sentence should leave that setting alone.

To extend the evaluation, add entries to these files. Real questions from
students would be the most useful addition.
