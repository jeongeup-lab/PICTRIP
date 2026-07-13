import { getSeenChannelsRaw, setSeenChannelsRaw } from "@/lib/storage";

type SeenPayload = { day: string; keys: string[] };

export async function loadSeen(today: string): Promise<string[]> {
  const raw = await getSeenChannelsRaw();
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as SeenPayload;
    return parsed.day === today ? parsed.keys : [];
  } catch {
    return [];
  }
}

export async function saveSeen(keys: string[], today: string): Promise<void> {
  await setSeenChannelsRaw(JSON.stringify({ day: today, keys }));
}
