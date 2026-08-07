export interface NotificationPrefs {
  savedNews: boolean;
  crowding: boolean;
  marketing: boolean;
}

export type NotificationTopic = keyof NotificationPrefs;

export const DEFAULT_NOTIFICATION_PREFS: NotificationPrefs = {
  savedNews: false,
  crowding: false,
  marketing: false,
};

export const NOTIFICATION_TOPICS: readonly {
  topic: NotificationTopic;
  title: string;
  sub: string;
}[] = [
  { topic: "savedNews", title: "저장한 곳 소식", sub: "축제·행사가 열릴 때" },
  { topic: "crowding", title: "혼잡도 알림", sub: "가려던 곳이 붐빌 때" },
  { topic: "marketing", title: "마케팅 정보", sub: "이벤트·혜택 안내" },
] as const;

export function parseNotificationPrefs(raw: string | null): NotificationPrefs {
  if (!raw) return DEFAULT_NOTIFICATION_PREFS;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return DEFAULT_NOTIFICATION_PREFS;
    const record = parsed as Record<string, unknown>;
    return {
      savedNews: record.savedNews === true,
      crowding: record.crowding === true,
      marketing: record.marketing === true,
    };
  } catch {
    return DEFAULT_NOTIFICATION_PREFS;
  }
}

export function serializeNotificationPrefs(prefs: NotificationPrefs): string {
  return JSON.stringify(prefs);
}
