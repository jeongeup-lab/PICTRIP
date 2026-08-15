export function htmlToPlainText(input: string): string {
  if (!input) return "";

  let text = input.replace(/<br\s*\/?>/gi, "\n").replace(/<\/(?:p|div|li)>/gi, "\n");

  text = stripTags(text);
  text = decodeEntities(text);

  return text.replace(/\n{3,}/g, "\n\n").trim();
}

function stripTags(input: string): string {
  let text = input;
  let prev: string;
  do {
    prev = text;
    text = text.replace(/<[^>]*>/g, "");
  } while (text !== prev);
  return text;
}

function decodeEntities(input: string): string {
  return input
    .replace(/&nbsp;/gi, " ")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#(\d+);/g, (_, code) => codePoint(code))
    .replace(/&amp;/gi, "&");
}

function codePoint(code: string): string {
  const n = Number(code);
  return Number.isFinite(n) && n > 0 ? String.fromCodePoint(n) : "";
}
