export interface AuthSession {
  getAccessToken: () => string | null;
  refresh: () => Promise<string>;
  clear: () => Promise<void>;
}

let session: AuthSession | null = null;

export function registerAuthSession(s: AuthSession): void {
  session = s;
}

export function getAuthSession(): AuthSession | null {
  return session;
}
