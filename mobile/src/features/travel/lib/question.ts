export const PHOTO_ONLY_QUESTION = "이 사진 같은 분위기의 여행지";

export const IDLE_SUGGESTIONS: readonly string[] = [
  "여름에 시원하고 사람 적은 계곡",
  "비 와도 갈 만한 실내",
  "반려견과 갈 만한 곳",
  "제주 2박 3일",
];

export const RETRY_SUGGESTION = "다시 시도";

export function composeQuestion(input: string, hasPhoto: boolean): string | null {
  const trimmed = input.trim();
  if (trimmed) return trimmed;
  return hasPhoto ? PHOTO_ONLY_QUESTION : null;
}

export function resultsTitle(question: string): string {
  const trimmed = question.trim();
  return trimmed.length > 20 ? `${trimmed.slice(0, 20)}…` : trimmed;
}
