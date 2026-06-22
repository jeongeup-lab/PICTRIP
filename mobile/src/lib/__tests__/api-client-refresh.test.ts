import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from "axios";
import type { Envelope } from "@/lib/api-types";
import { AppError } from "@/lib/app-error";
import { handleResponseError } from "@/lib/api-client";

const refresh = jest.fn();
// `mock`-prefixed so the hoisted jest.mock factory may reference it.
const mockGetState = jest.fn(() => ({ accessToken: "old", refresh }));

// jest.mock is hoisted above the imports by babel-plugin-jest-hoist.
jest.mock("@/features/auth/stores/auth-store", () => ({
  useAuthStore: { getState: () => mockGetState() },
}));

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

function makeConfig(overrides: Partial<RetriableConfig> = {}): RetriableConfig {
  return {
    headers: new AxiosHeaders({ Authorization: "Bearer old" }),
    ...overrides,
  } as RetriableConfig;
}

function makeError(
  status: number,
  code: string,
  config?: RetriableConfig,
): AxiosError<Envelope<unknown>> {
  const err = new AxiosError<Envelope<unknown>>("request failed");
  err.config = config as never;
  err.response = {
    status,
    statusText: "",
    headers: {},
    config: config as never,
    data: { data: null, error: { code, message: "x" }, meta: null } as never,
  };
  return err;
}

function networkError(): AxiosError<Envelope<unknown>> {
  const err = new AxiosError<Envelope<unknown>>("no response");
  err.response = undefined;
  return err;
}

describe("handleResponseError (401 refresh-retry interceptor)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetState.mockReturnValue({ accessToken: "old", refresh });
  });

  it("refreshes once and retries with the new bearer on AUTH_TOKEN_EXPIRED", async () => {
    refresh.mockResolvedValue("new");
    const retry = jest.fn().mockResolvedValue("RETRY_RESULT");
    const config = makeConfig();
    const result = await handleResponseError(makeError(401, "AUTH_TOKEN_EXPIRED", config), retry);

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(result).toBe("RETRY_RESULT");
    expect(retry).toHaveBeenCalledTimes(1);
    const retried = retry.mock.calls[0][0] as RetriableConfig;
    expect(retried._retried).toBe(true);
    expect(retried.headers.get("Authorization")).toBe("Bearer new");
  });

  it("does not refresh again and throws when the request was already retried", async () => {
    const retry = jest.fn();
    const config = makeConfig({ _retried: true });
    await expect(
      handleResponseError(makeError(401, "AUTH_TOKEN_EXPIRED", config), retry),
    ).rejects.toMatchObject({ code: "AUTH_TOKEN_EXPIRED" });

    expect(refresh).not.toHaveBeenCalled();
    expect(retry).not.toHaveBeenCalled();
  });

  it("throws the ORIGINAL AUTH_TOKEN_EXPIRED AppError when refresh rejects", async () => {
    refresh.mockRejectedValue(new Error("refresh boom"));
    const retry = jest.fn();
    const config = makeConfig();
    await expect(
      handleResponseError(makeError(401, "AUTH_TOKEN_EXPIRED", config), retry),
    ).rejects.toMatchObject({
      code: "AUTH_TOKEN_EXPIRED",
    });

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(retry).not.toHaveBeenCalled();
  });

  it("rethrows a non-401 / non-AUTH_TOKEN_EXPIRED error without calling refresh", async () => {
    const retry = jest.fn();
    const config = makeConfig();
    const promise = handleResponseError(makeError(500, "INTERNAL_ERROR", config), retry);
    await expect(promise).rejects.toBeInstanceOf(AppError);
    await expect(promise).rejects.toMatchObject({ code: "INTERNAL_ERROR" });

    expect(refresh).not.toHaveBeenCalled();
    expect(retry).not.toHaveBeenCalled();
  });

  it("throws a NETWORK_ERROR AppError when there is no response", async () => {
    const retry = jest.fn();
    const promise = handleResponseError(networkError(), retry);
    await expect(promise).rejects.toBeInstanceOf(AppError);
    await expect(promise).rejects.toMatchObject({ code: "NETWORK_ERROR" });

    expect(refresh).not.toHaveBeenCalled();
    expect(retry).not.toHaveBeenCalled();
  });
});
