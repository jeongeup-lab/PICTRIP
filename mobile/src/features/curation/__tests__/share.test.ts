import { Share } from "react-native";
import { curationShareUrl, shareCuration } from "@/features/curation/share";

describe("curation share", () => {
  it("builds the web deep link from the slug", () => {
    expect(curationShareUrl("jeju")).toBe("https://pictrip.org/curations/jeju");
  });

  it("shares the flattened title plus the deep link", async () => {
    const shareSpy = jest
      .spyOn(Share, "share")
      .mockResolvedValue({ action: Share.dismissedAction } as never);

    await shareCuration("제주, 매일 가도\n새로운 섬", "jeju");

    expect(shareSpy).toHaveBeenCalledTimes(1);
    const [content] = shareSpy.mock.calls[0]!;
    const payload = JSON.stringify(content);
    expect(payload).toContain("제주, 매일 가도 새로운 섬");
    expect(payload).toContain("https://pictrip.org/curations/jeju");
    expect(payload).not.toContain("\\n새로운");
    shareSpy.mockRestore();
  });
});
