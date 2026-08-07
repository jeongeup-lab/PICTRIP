import { useNotificationPrefs } from "@/features/profile/stores/notification-prefs-store";
import { getNotificationPrefsRaw, setNotificationPrefsRaw } from "@/lib/storage";
import { DEFAULT_NOTIFICATION_PREFS } from "@/features/profile/lib/notification-prefs";

jest.mock("@/lib/storage", () => ({
  getNotificationPrefsRaw: jest.fn(),
  setNotificationPrefsRaw: jest.fn(),
}));

const readRaw = getNotificationPrefsRaw as jest.Mock;
const writeRaw = setNotificationPrefsRaw as jest.Mock;

beforeEach(() => {
  useNotificationPrefs.setState({ prefs: DEFAULT_NOTIFICATION_PREFS, hydrated: false });
  jest.clearAllMocks();
  writeRaw.mockResolvedValue(undefined);
});

describe("useNotificationPrefs", () => {
  it("keeps a toggle the user made while the stored value was still loading", async () => {
    let release: (value: string | null) => void = () => undefined;
    readRaw.mockReturnValue(
      new Promise<string | null>((resolve) => {
        release = resolve;
      }),
    );

    const hydrating = useNotificationPrefs.getState().hydrate();
    useNotificationPrefs.getState().toggle("savedNews", true);
    release(JSON.stringify({ savedNews: false, crowding: false, marketing: false }));
    await hydrating;

    expect(useNotificationPrefs.getState().prefs.savedNews).toBe(true);
  });

  it("takes the stored value when nothing was toggled first", async () => {
    readRaw.mockResolvedValue(
      JSON.stringify({ savedNews: true, crowding: false, marketing: false }),
    );

    await useNotificationPrefs.getState().hydrate();

    expect(useNotificationPrefs.getState().prefs.savedNews).toBe(true);
  });

  it("writes every toggle through to storage", () => {
    useNotificationPrefs.getState().toggle("crowding", true);

    expect(writeRaw).toHaveBeenCalledWith(
      JSON.stringify({ savedNews: false, crowding: true, marketing: false }),
    );
  });
});
