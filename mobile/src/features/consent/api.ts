import { api } from "@/lib/api-client";
import type { ConsentPutBody, ConsentState } from "@/features/consent/types";

/** The api-client response interceptor unwraps the JSend envelope, so these
 * resolve to the `data` payload. Cast mirrors features/saved/api.ts exactly. */
export async function getConsents(): Promise<ConsentState> {
  return (await api.get("/users/me/consents")) as unknown as ConsentState;
}

export async function putConsents(body: ConsentPutBody): Promise<ConsentState> {
  return (await api.put("/users/me/consents", body)) as unknown as ConsentState;
}
