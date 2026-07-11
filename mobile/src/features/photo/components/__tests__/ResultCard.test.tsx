import renderer, { act } from "react-test-renderer";
import { ResultCard } from "@/features/photo/components/ResultCard";
import type { PhotoMatch } from "@/lib/api-types";

const base: PhotoMatch = {
  contentId: "1",
  title: "곽지해수욕장",
  firstImageUrl: null,
  category: "해변",
  similarity: 0.96,
  distance: 3400,
  regionName: "제주",
  sigunguName: "제주시",
};

async function render(el: React.ReactElement) {
  let r: renderer.ReactTestRenderer;
  await act(async () => {
    r = renderer.create(el);
  });
  return JSON.stringify(r!.toJSON());
}

describe("ResultCard", () => {
  it("shows name, category·region, distance and similarity percent when showDistance", async () => {
    const tree = await render(<ResultCard match={base} showDistance onPress={() => {}} />);
    expect(tree).toContain("곽지해수욕장");
    expect(tree).toContain("해변 · 제주 제주시 · 3.4km");
    expect(tree).toContain("96%");
    expect(tree).toContain("유사도");
  });
  it("omits distance when showDistance is false", async () => {
    const tree = await render(<ResultCard match={base} showDistance={false} onPress={() => {}} />);
    expect(tree).toContain("해변 · 제주 제주시");
    expect(tree).not.toContain("3.4km");
  });
  it("omits distance when distance is null even if showDistance", async () => {
    const tree = await render(
      <ResultCard match={{ ...base, distance: null }} showDistance onPress={() => {}} />,
    );
    expect(tree).not.toContain("km");
  });
  it("shows a BEST badge only on rank 0", async () => {
    const best = await render(<ResultCard match={base} showDistance rank={0} onPress={() => {}} />);
    expect(best).toContain("BEST");
    const other = await render(
      <ResultCard match={base} showDistance rank={2} onPress={() => {}} />,
    );
    expect(other).not.toContain("BEST");
  });
  it("hides the BEST badge on rank 0 when showBest is false (distance sort)", async () => {
    const tree = await render(
      <ResultCard match={base} showDistance rank={0} showBest={false} onPress={() => {}} />,
    );
    expect(tree).not.toContain("BEST");
  });
});
