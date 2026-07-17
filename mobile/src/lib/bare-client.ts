import { create as axiosCreate, AxiosError, AxiosResponse } from "axios";
import { API_BASE } from "@/constants/env";
import type { Envelope } from "@/lib/api-types";
import { unwrapData, envelopeToError } from "@/lib/jsend";
import { AppError } from "@/lib/app-error";

export const bareClient = axiosCreate({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

bareClient.interceptors.response.use(
  ((response: AxiosResponse<Envelope<unknown>>): unknown => unwrapData(response.data)) as (
    r: AxiosResponse,
  ) => AxiosResponse,
  (error: AxiosError<Envelope<unknown>>) => {
    if (error.response) {
      throw envelopeToError(error.response.data, error.response.status);
    }
    throw new AppError("NETWORK_ERROR", "네트워크에 연결할 수 없습니다.", 0);
  },
);
