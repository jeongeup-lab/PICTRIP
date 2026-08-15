import renderer, { act } from "react-test-renderer";
import { WelcomeBubble, WELCOME_TEXT } from "@/features/travel/components/WelcomeBubble";

describe("WelcomeBubble", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("타이핑이 끝나면 인사말 전체가 남는다", async () => {
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(<WelcomeBubble />);
    });

    act(() => {
      jest.advanceTimersByTime(WELCOME_TEXT.length * 40 + 100);
    });

    expect(JSON.stringify(tree!.toJSON())).toContain("뭐든 물어보세요.");
    await act(async () => tree!.unmount());
  });

  it("처음에는 글자를 점진적으로 드러낸다", async () => {
    let tree: renderer.ReactTestRenderer;
    await act(async () => {
      tree = renderer.create(<WelcomeBubble />);
    });

    act(() => {
      jest.advanceTimersByTime(28 * 3);
    });

    const out = JSON.stringify(tree!.toJSON());
    expect(out).toContain("안녕");
    expect(out).not.toContain("물어보세요");
    await act(async () => tree!.unmount());
  });
});
