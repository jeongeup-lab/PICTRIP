const HANGUL_FIRST = 0xac00;
const HANGUL_LAST = 0xd7a3;
const JONGSEONG_COUNT = 28;

export function withObjectParticle(word: string): string {
  const trimmed = word.trim();
  const code = trimmed.slice(-1).charCodeAt(0);
  const isHangul = code >= HANGUL_FIRST && code <= HANGUL_LAST;
  const hasFinal = isHangul && (code - HANGUL_FIRST) % JONGSEONG_COUNT !== 0;
  return `${trimmed}${hasFinal ? "을" : "를"}`;
}

export function unsaveMessage(title: string): string {
  return `${withObjectParticle(title)} 스크랩에서 뺐어요`;
}
