export interface ConsentState {
  locationConsent: boolean;
  termsVersion: string | null;
  consentedAt: string | null;
}

export interface ConsentPutBody {
  locationConsent: boolean;
  termsVersion: string;
}
