// An answer's text carries its sources as markers such as "[2]". This splits
// the text so the markers can be drawn as links to the list of sources.

export type AnswerPart =
  { kind: "text"; text: string } | { kind: "citation"; number: number };

export function splitCitations(answer: string): AnswerPart[] {
  const parts: AnswerPart[] = [];
  let position = 0;
  for (const match of answer.matchAll(/\[(\d+)\]/g)) {
    if (match.index > position) {
      parts.push({ kind: "text", text: answer.slice(position, match.index) });
    }
    parts.push({ kind: "citation", number: Number(match[1]) });
    position = match.index + match[0].length;
  }
  if (position < answer.length) {
    parts.push({ kind: "text", text: answer.slice(position) });
  }
  return parts;
}
