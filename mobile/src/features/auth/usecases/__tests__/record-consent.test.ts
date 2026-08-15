import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import { putConsents } from "@/features/consent/api";

jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ granted: true }),
}));
jest.mock("@/features/consent/api", () => ({
  putConsents: jest.fn(),
}));
jest.mock("@/constants/legal", () => ({ TERMS_VERSION: "2026-06-22" }));

const mockPut = putConsents as jest.MockedFunction<typeof putConsents>;

describe("recordConsentSnapshot", () => {
  beforeEach(() => jest.clearAllMocks());

  it("records the OS location grant and the current terms version", async () => {
    mockPut.mockResolvedValue({
      locationConsent: true,
      termsVersion: "2026-06-22",
      consentedAt: "2026-06-22T00:00:00Z",
    });

    await recordConsentSnapshot();

    expect(mockPut).toHaveBeenCalledWith({
      locationConsent: true,
      termsVersion: "2026-06-22",
    });
  });
});
