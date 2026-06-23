/** Mirror of backend ConsentState (GET /users/me/consents). */
export interface ConsentState {
  locationConsent: boolean;
  photoConsent: boolean;
  termsVersion: string | null;
  consentedAt: string | null;
}

/** Body for PUT /users/me/consents (all three fields required). */
export interface ConsentPutBody {
  locationConsent: boolean;
  photoConsent: boolean;
  termsVersion: string;
}
