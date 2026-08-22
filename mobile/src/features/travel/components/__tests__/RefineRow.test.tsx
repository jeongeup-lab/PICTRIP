import type React from "react";
import { Text } from "react-native";
import renderer, { act } from "react-test-renderer";

import type { Suggestion } from "@/features/travel/api";
import { RefineRow, RETRY_LEAD } from "@/features/travel/components/RefineRow";

const loosen: Suggestion = { label: "실내 빼기", patch: { drop: "indoor" } };
const tighten: Suggestion = { label: "한적한 곳으로", patch: { crowdPreference: "quiet" } };

function draw(node: React.ReactElement): renderer.ReactTestRenderer {
  let tree: renderer.ReactTestRenderer | undefined;
  act(() => {
    tree = renderer.create(node);
  });
  return tree as renderer.ReactTestRenderer;
}

function labels(tree: renderer.ReactTestRenderer): string[] {
  return tree.root
    .findAllByType(Text)
    .map((node) => node.props.children)
    .filter((child): child is string => typeof child === "string");
}

it("조건을 푸는 제안만 칩으로 남기고 무엇을 하는 줄인지 밝힌다", () => {
  const tree = draw(<RefineRow refinements={[loosen, tighten]} onRefine={jest.fn()} />);

  expect(labels(tree)).toEqual([RETRY_LEAD, "실내 빼기"]);
});

it("칩을 누르면 그 축을 빼는 patch 가 나간다", () => {
  const onRefine = jest.fn();
  const tree = draw(<RefineRow refinements={[loosen]} onRefine={onRefine} />);

  const chip = tree.root.findAll(
    (node) => node.props.accessibilityLabel === "실내 빼기, 눌러서 다시 찾기",
  )[0];
  act(() => {
    chip.props.onPress();
  });

  expect(onRefine).toHaveBeenCalledWith({ drop: "indoor" });
});

it("보여줄 게 없으면 줄 자체를 그리지 않는다", () => {
  const tree = draw(<RefineRow refinements={[tighten]} onRefine={jest.fn()} />);

  expect(tree.root.findAllByProps({ testID: "travel-refinements" })).toHaveLength(0);
});
