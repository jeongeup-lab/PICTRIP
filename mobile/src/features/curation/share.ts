import { Platform, Share } from "react-native";

/** Web deep-link base for curation detail (S02 §06 이탈-공유; web fallback
 * pages live under pictrip.org/curations/…). URL sharing only — KTO-safe. */
export const CURATION_SHARE_BASE = "https://pictrip.org/curations";

export function curationShareUrl(slug: string): string {
  return `${CURATION_SHARE_BASE}/${slug}`;
}

/** Open the OS share sheet with the curation title + deep link. The title keeps
 * editorial line breaks (`\n`) for rendering — flatten them for share text.
 * iOS reads a separate `url` field; Android only reads `message`, so the link
 * is inlined there. Dismissal/failure is non-fatal. */
export async function shareCuration(title: string, slug: string): Promise<void> {
  const flatTitle = title.replace(/\n/g, " ");
  const url = curationShareUrl(slug);
  try {
    await Share.share(
      Platform.OS === "ios"
        ? { title: flatTitle, message: flatTitle, url }
        : { title: flatTitle, message: `${flatTitle}\n${url}` },
    );
  } catch {
    // user dismissed or the share sheet is unavailable — nothing to surface
  }
}
