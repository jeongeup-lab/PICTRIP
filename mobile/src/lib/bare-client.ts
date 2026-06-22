import { create as axiosCreate, AxiosError } from "axios";
import { API_BASE } from "@/constants/env";
import type { Envelope } from "@/lib/api-types";
import { unwrapData, envelopeToError } from "@/lib/jsend";
import { AppError } from "@/lib/app-error";

/** Unauthed client for /auth/* — unwraps JSend, throws AppError. No token, no retry. */
export const bareClient = axiosCreate({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

/* The interceptor intentionally returns unwrapped data (not AxiosResponse).
   Callers cast the result at call-site (e.g. `as unknown as TokenPair`). */
(bareClient.interceptors.response as any).use(
  (response: { data: Envelope<unknown> }) => unwrapData(response.data),
  (error: AxiosError<Envelope<unknown>>) => {
    if (error.response) {
      throw envelopeToError(error.response.data, error.response.status);
    }
    throw new AppError("NETWORK_ERROR", "네트워크에 연결할 수 없습니다.", 0);
  },
);
