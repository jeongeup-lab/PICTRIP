import * as Location from "expo-location";
import { api } from "@/lib/api-client";
import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";

jest.mock("expo-location", () => ({ getForegroundPermissionsAsync: jest.fn() }));
jest.mock("@/lib/api-client", () => ({ api: { put: jest.fn() } }));
jest.mock("@/constants/legal", () => ({ TERMS_VERSION: "2026-06-22" }));

describe("recordConsentSnapshot", () => {
  beforeEach(() => jest.clearAllMocks());

  it("PUTs locationConsent=true when permission granted", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: true });
    (api.put as jest.Mock).mockResolvedValue({});
    await recordConsentSnapshot();
    expect(api.put).toHaveBeenCalledWith("/users/me/consents", {
      locationConsent: true,
      photoConsent: false,
      termsVersion: "2026-06-22",
    });
  });

  it("PUTs locationConsent=false when not granted", async () => {
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ granted: false });
    (api.put as jest.Mock).mockResolvedValue({});
    await recordConsentSnapshot();
    expect(api.put).toHaveBeenCalledWith(
      "/users/me/consents",
      expect.objectContaining({ locationConsent: false }),
    );
  });
});
