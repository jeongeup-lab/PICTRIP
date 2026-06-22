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
  it("shows name, category·region, distance and bucket label when showDistance", async () => {
    const tree = await render(<ResultCard match={base} showDistance onPress={() => {}} />);
    expect(tree).toContain("곽지해수욕장");
    expect(tree).toContain("해변 · 제주 제주시 · 3.4km");
    expect(tree).toContain("매우 닮음");
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
});
