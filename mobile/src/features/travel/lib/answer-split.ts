import type { AnswerPart } from "@/features/travel/api";

const SENTENCE_END = /[.?!](?=\s|$)/;

export interface SplitAnswer {
  lead: AnswerPart[];
  rest: AnswerPart[];
}

function withoutLeadingBlanks(parts: AnswerPart[]): AnswerPart[] {
  let start = 0;
  while (start < parts.length && parts[start].text.trim() === "") start += 1;
  const rest = parts.slice(start);
  const first = rest[0];
  return first ? [{ ...first, text: first.text.trimStart() }, ...rest.slice(1)] : rest;
}

export function splitAnswer(parts: AnswerPart[]): SplitAnswer {
  const lead: AnswerPart[] = [];

  for (let index = 0; index < parts.length; index += 1) {
    const part = parts[index];
    const at = part.text.search(SENTENCE_END);
    if (at === -1) {
      lead.push(part);
      continue;
    }
    const head = part.text.slice(0, at + 1);
    const tail = part.text.slice(at + 1).trimStart();
    if (head) lead.push({ ...part, text: head });
    const following = withoutLeadingBlanks(parts.slice(index + 1));
    return { lead, rest: tail ? [{ ...part, text: tail }, ...following] : following };
  }

  return { lead, rest: [] };
}
