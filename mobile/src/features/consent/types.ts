export interface ConsentState {
  locationConsent: boolean;
  photoConsent: boolean;
  termsVersion: string | null;
  consentedAt: string | null;
}

export interface ConsentPutBody {
  locationConsent: boolean;
  photoConsent: boolean;
  termsVersion: string;
}
