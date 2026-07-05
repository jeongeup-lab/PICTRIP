/** Lib-level auth session seam.
 *
 * api-client (lib layer) must not import the auth feature (inverted
 * dependency), so the auth store registers its live handle here at module
 * init — the entry route (`src/app/index.tsx`) imports the store before any
 * authed request can fire. When no handle is registered (unit tests, early
 * boot) requests go out unauthenticated and 401s surface as-is.
 */
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
