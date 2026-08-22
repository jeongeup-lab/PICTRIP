export interface ConsentState {
  locationConsent: boolean;
  termsVersion: string | null;
  consentedAt: string | null;
  aiTransferConsent: boolean;
  aiTransferVersion: string | null;
  aiTransferConsentedAt: string | null;
}

export interface AiTransferConsentBody {
  granted: boolean;
  version: string;
}

export interface ConsentPutBody {
  locationConsent: boolean;
  termsVersion: string;
}
