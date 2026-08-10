export const PHOTO_ONLY_QUESTION = "이 사진 같은 분위기의 여행지";

export function composeQuestion(input: string, hasPhoto: boolean): string | null {
  const trimmed = input.trim();
  if (trimmed) return trimmed;
  return hasPhoto ? PHOTO_ONLY_QUESTION : null;
}
