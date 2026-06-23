import { bareClient } from "@/lib/bare-client";
import { api } from "@/lib/api-client";
import { oauthLogin, logoutRequest, deleteAccountRequest } from "@/features/auth/api";

jest.mock("@/lib/bare-client", () => ({ bareClient: { post: jest.fn() } }));
jest.mock("@/lib/api-client", () => ({ api: { delete: jest.fn() } }));

describe("auth api", () => {
  beforeEach(() => jest.clearAllMocks());

  it("oauthLogin posts idToken+nonce to the provider path and returns the pair", async () => {
    const pair = { accessToken: "a", refreshToken: "r", expiresIn: 900, user: { id: 1 } };
    (bareClient.post as jest.Mock).mockResolvedValue(pair);
    const res = await oauthLogin("kakao", "tok", "n1");
    expect(bareClient.post).toHaveBeenCalledWith("/auth/oauth/kakao", {
      idToken: "tok",
      nonce: "n1",
    });
    expect(res).toBe(pair);
  });

  it("logoutRequest posts the refresh token", async () => {
    (bareClient.post as jest.Mock).mockResolvedValue({});
    await logoutRequest("r1");
    expect(bareClient.post).toHaveBeenCalledWith("/auth/logout", { refreshToken: "r1" });
  });

  it("deleteAccountRequest calls authed DELETE /users/me", async () => {
    (api.delete as jest.Mock).mockResolvedValue(undefined);
    await deleteAccountRequest();
    expect(api.delete).toHaveBeenCalledWith("/users/me");
  });
});
