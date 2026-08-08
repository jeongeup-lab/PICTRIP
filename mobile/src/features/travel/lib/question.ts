export const PHOTO_ONLY_QUESTION = "이 사진 같은 분위기의 여행지";

export const MY_LOCATION = "내 위치";

export function composeQuestion(input: string, hasPhoto: boolean): string | null {
  const trimmed = input.trim();
  if (trimmed) return trimmed;
  return hasPhoto ? PHOTO_ONLY_QUESTION : null;
}

export function anchorQuestion(title: string, chipLabel: string): string {
  return `${title} ${chipLabel}`;
}
