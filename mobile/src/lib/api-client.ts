import {
  create as axiosCreate,
  AxiosError,
  AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { API_BASE } from "@/constants/env";
import type { Envelope } from "@/lib/api-types";
import { unwrapData, envelopeToError } from "@/lib/jsend";
import { AppError } from "@/lib/app-error";
import { useAuthStore } from "@/features/auth/stores/auth-store";

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

/** Authed client — injects Bearer from auth-store, unwraps JSend, throws AppError.
   On 401 AUTH_TOKEN_EXPIRED it refreshes once and retries the original request. */
export const api = axiosCreate({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

/* Same contained typing as bare-client: the fulfilled handler returns unwrapped
   envelope data (not AxiosResponse). axios types the fulfilled return as
   AxiosResponse, so the handler is cast at function level only — no `as any`,
   no cast on the interceptor manager; runtime returns the data unchanged. */
api.interceptors.response.use(
  ((response: AxiosResponse<Envelope<unknown>>): unknown => unwrapData(response.data)) as (
    r: AxiosResponse,
  ) => AxiosResponse,
  async (error: AxiosError<Envelope<unknown>>) => {
    if (!error.response) {
      throw new AppError("NETWORK_ERROR", "네트워크에 연결할 수 없습니다.", 0);
    }
    const appError = envelopeToError(error.response.data, error.response.status);
    const config = error.config as RetriableConfig | undefined;

    if (appError.code === "AUTH_TOKEN_EXPIRED" && config && !config._retried) {
      config._retried = true;
      try {
        const newToken = await useAuthStore.getState().refresh();
        config.headers.set("Authorization", `Bearer ${newToken}`);
        return api.request(config);
      } catch {
        throw appError;
      }
    }
    throw appError;
  },
);
