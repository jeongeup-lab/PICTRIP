import {
  DEFAULT_NOTIFICATION_PREFS,
  parseNotificationPrefs,
  serializeNotificationPrefs,
} from "@/features/profile/lib/notification-prefs";

describe("parseNotificationPrefs", () => {
  it("defaults to everything off", () => {
    expect(parseNotificationPrefs(null)).toEqual(DEFAULT_NOTIFICATION_PREFS);
    expect(parseNotificationPrefs("")).toEqual(DEFAULT_NOTIFICATION_PREFS);
  });

  it("ignores broken or non-object payloads", () => {
    expect(parseNotificationPrefs("{oops")).toEqual(DEFAULT_NOTIFICATION_PREFS);
    expect(parseNotificationPrefs("null")).toEqual(DEFAULT_NOTIFICATION_PREFS);
    expect(parseNotificationPrefs('"on"')).toEqual(DEFAULT_NOTIFICATION_PREFS);
  });

  it("reads only strict booleans", () => {
    expect(parseNotificationPrefs('{"savedNews":true,"crowding":"yes","marketing":1}')).toEqual({
      savedNews: true,
      crowding: false,
      marketing: false,
    });
  });

  it("round-trips", () => {
    const prefs = { savedNews: true, crowding: false, marketing: true };
    expect(parseNotificationPrefs(serializeNotificationPrefs(prefs))).toEqual(prefs);
  });
});
