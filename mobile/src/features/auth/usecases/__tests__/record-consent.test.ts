import { recordConsentSnapshot } from "@/features/auth/usecases/record-consent";
import { getConsents, putConsents } from "@/features/consent/api";

jest.mock("expo-location", () => ({
  getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ granted: true }),
}));
jest.mock("@/features/consent/api", () => ({
  getConsents: jest.fn(),
  putConsents: jest.fn(),
}));
jest.mock("@/constants/legal", () => ({ TERMS_VERSION: "2026-06-22" }));

const mockGet = getConsents as jest.MockedFunction<typeof getConsents>;
const mockPut = putConsents as jest.MockedFunction<typeof putConsents>;

describe("recordConsentSnapshot", () => {
  beforeEach(() => jest.clearAllMocks());

  it("preserves existing photoConsent and records OS location + current terms", async () => {
    mockGet.mockResolvedValue({
      locationConsent: false,
      photoConsent: true,
      termsVersion: "2026-01-01",
      consentedAt: "2026-01-01T00:00:00Z",
    });
    mockPut.mockResolvedValue({
      locationConsent: true,
      photoConsent: true,
      termsVersion: "2026-06-22",
      consentedAt: "2026-06-22T00:00:00Z",
    });

    await recordConsentSnapshot();

    expect(mockGet).toHaveBeenCalled();
    expect(mockPut).toHaveBeenCalledWith({
      locationConsent: true,
      photoConsent: true,
      termsVersion: "2026-06-22",
    });
  });
});
