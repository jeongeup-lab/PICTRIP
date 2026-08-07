import { create } from "zustand";
import { getNotificationPrefsRaw, setNotificationPrefsRaw } from "@/lib/storage";
import {
  DEFAULT_NOTIFICATION_PREFS,
  parseNotificationPrefs,
  serializeNotificationPrefs,
  type NotificationPrefs,
  type NotificationTopic,
} from "@/features/profile/lib/notification-prefs";

interface NotificationPrefsState {
  prefs: NotificationPrefs;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  toggle: (topic: NotificationTopic, next: boolean) => void;
}

export const useNotificationPrefs = create<NotificationPrefsState>((set, get) => ({
  prefs: DEFAULT_NOTIFICATION_PREFS,
  hydrated: false,
  hydrate: async () => {
    if (get().hydrated) return;
    try {
      const raw = await getNotificationPrefsRaw();
      if (get().hydrated) return;
      set({ prefs: parseNotificationPrefs(raw), hydrated: true });
    } catch {
      set({ hydrated: true });
    }
  },
  toggle: (topic, next) => {
    const prefs = { ...get().prefs, [topic]: next };
    set({ prefs, hydrated: true });
    void setNotificationPrefsRaw(serializeNotificationPrefs(prefs)).catch(() => undefined);
  },
}));
