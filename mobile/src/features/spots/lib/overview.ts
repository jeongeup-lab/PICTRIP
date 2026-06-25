/** First sentence of overview, trimmed — used as the centered hero lead. */
export function firstSentence(text: string | null): string | null {
  if (!text) return null;
  const match = text.trim().match(/^[\s\S]*?[.!?。]/);
  return (match ? match[0] : text).trim() || null;
}
