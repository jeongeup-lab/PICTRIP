import { File, Paths } from "expo-file-system";
import type { SpotCard } from "@/lib/api-types";

const GUEST_SAVED_FILE = "guest_saved.json";

export async function readGuestSaved(): Promise<SpotCard[]> {
  try {
    const file = new File(Paths.document, GUEST_SAVED_FILE);
    if (!file.exists) return [];
    const parsed = JSON.parse(await file.text());
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function writeGuestSaved(spots: SpotCard[]): Promise<void> {
  try {
    const file = new File(Paths.document, GUEST_SAVED_FILE);
    if (!file.exists) file.create();
    file.write(JSON.stringify(spots));
  } catch {
    return;
  }
}
