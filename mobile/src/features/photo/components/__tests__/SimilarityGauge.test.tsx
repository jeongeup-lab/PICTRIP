import renderer, { act } from "react-test-renderer";
import { SimilarityGauge } from "@/features/photo/components/SimilarityGauge";

async function render(el: React.ReactElement) {
  let r: renderer.ReactTestRenderer;
  await act(async () => {
    r = renderer.create(el);
  });
  return r!;
}

describe("SimilarityGauge", () => {
  it("shows the bucket label for a high similarity", async () => {
    const r = await render(<SimilarityGauge similarity={0.92} />);
    expect(JSON.stringify(r.toJSON())).toContain("매우 닮음");
  });
  it("shows 비슷함 for a low similarity", async () => {
    const r = await render(<SimilarityGauge similarity={0.4} />);
    expect(JSON.stringify(r.toJSON())).toContain("비슷함");
  });
});
