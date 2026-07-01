/**
 * Convert a fragment of HTML (KTO `overview` text sometimes ships raw <br>, <p>,
 * and entities) into readable plain text. DISPLAY-ONLY — never mutate what is
 * stored or sent; use this at render time only.
 */
export function htmlToPlainText(input: string): string {
  if (!input) return "";

  let text = input
    // line-break / block-close tags become newlines
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(?:p|div|li)>/gi, "\n");

  // strip every remaining tag
  text = stripTags(text);
  text = decodeEntities(text);

  return (
    text
      // collapse runs of 3+ newlines down to a paragraph break
      .replace(/\n{3,}/g, "\n\n")
      .trim()
  );
}

// Strip HTML tags to a fixpoint. A single `<[^>]*>` pass can leave a
// reconstructable tag behind (e.g. "<<b>script>" -> "<script>"), so repeat
// until the string stops changing — complete, bypass-proof sanitization.
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
  return (
    input
      .replace(/&nbsp;/gi, " ")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/&quot;/gi, '"')
      // numeric entities (covers &#39; and any other &#NNN;)
      .replace(/&#(\d+);/g, (_, code) => codePoint(code))
      // &amp; last so "&amp;lt;" decodes to the literal "&lt;", not "<"
      .replace(/&amp;/gi, "&")
  );
}

function codePoint(code: string): string {
  const n = Number(code);
  return Number.isFinite(n) && n > 0 ? String.fromCodePoint(n) : "";
}
