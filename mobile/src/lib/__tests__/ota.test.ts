import * as Updates from "expo-updates";
import { applyPendingUpdate } from "@/lib/ota";
import { bundleLabel, EMBEDDED_BUNDLE_LABEL } from "@/lib/app-meta";

jest.mock("expo-updates", () => ({
  isEnabled: true,
  updateId: null,
  checkForUpdateAsync: jest.fn(),
  fetchUpdateAsync: jest.fn(),
  reloadAsync: jest.fn(),
}));

const updates = Updates as jest.Mocked<typeof Updates> & { isEnabled: boolean };

describe("applyPendingUpdate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    updates.isEnabled = true;
  });

  it("새 업데이트가 있으면 받아서 즉시 재시작한다", async () => {
    updates.checkForUpdateAsync.mockResolvedValue({ isAvailable: true } as never);
    updates.fetchUpdateAsync.mockResolvedValue({ isNew: true } as never);

    await expect(applyPendingUpdate()).resolves.toBe(true);
    expect(updates.reloadAsync).toHaveBeenCalled();
  });

  it("업데이트가 없으면 재시작하지 않는다", async () => {
    updates.checkForUpdateAsync.mockResolvedValue({ isAvailable: false } as never);

    await expect(applyPendingUpdate()).resolves.toBe(false);
    expect(updates.fetchUpdateAsync).not.toHaveBeenCalled();
    expect(updates.reloadAsync).not.toHaveBeenCalled();
  });

  it("받아온 번들이 새것이 아니면 재시작하지 않는다", async () => {
    updates.checkForUpdateAsync.mockResolvedValue({ isAvailable: true } as never);
    updates.fetchUpdateAsync.mockResolvedValue({ isNew: false } as never);

    await expect(applyPendingUpdate()).resolves.toBe(false);
    expect(updates.reloadAsync).not.toHaveBeenCalled();
  });

  it("업데이트가 꺼진 빌드에서는 조회조차 하지 않는다", async () => {
    updates.isEnabled = false;

    await expect(applyPendingUpdate()).resolves.toBe(false);
    expect(updates.checkForUpdateAsync).not.toHaveBeenCalled();
  });

  it("조회가 실패해도 앱을 막지 않는다", async () => {
    updates.checkForUpdateAsync.mockRejectedValue(new Error("offline"));

    await expect(applyPendingUpdate()).resolves.toBe(false);
    expect(updates.reloadAsync).not.toHaveBeenCalled();
  });
});

describe("bundleLabel", () => {
  it("OTA 번들은 앞 8자리로 구분한다", () => {
    expect(bundleLabel("019fe989-9986-71bd-89b2-5485c12e758b")).toBe("019fe989");
  });

  it("내장 번들이면 내장이라고 표시한다", () => {
    expect(bundleLabel(null)).toBe(EMBEDDED_BUNDLE_LABEL);
  });
});
