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
import { getAuthSession } from "@/lib/auth-session";

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

export async function handleResponseError(
  error: AxiosError<Envelope<unknown>>,
  retry: (config: RetriableConfig) => Promise<unknown> = (config) => api.request(config),
): Promise<unknown> {
  if (!error.response) {
    throw new AppError("NETWORK_ERROR", "네트워크에 연결할 수 없습니다.", 0);
  }
  const appError = envelopeToError(error.response.data, error.response.status);
  const config = error.config as RetriableConfig | undefined;
  const session = getAuthSession();

  if (appError.code === "AUTH_TOKEN_EXPIRED" && session && config && !config._retried) {
    config._retried = true;
    try {
      const newToken = await session.refresh();
      config.headers.set("Authorization", `Bearer ${newToken}`);
      return retry(config);
    } catch {
      throw appError;
    }
  }
  if (appError.code === "AUTH_TOKEN_INVALID" || appError.code === "AUTH_SESSION_REVOKED") {
    void session?.clear();
  }
  throw appError;
}

export const api = axiosCreate({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getAuthSession()?.getAccessToken() ?? null;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

api.interceptors.response.use(
  ((response: AxiosResponse<Envelope<unknown>>): unknown => unwrapData(response.data)) as (
    r: AxiosResponse,
  ) => AxiosResponse,
  (error: AxiosError<Envelope<unknown>>) => handleResponseError(error),
);
