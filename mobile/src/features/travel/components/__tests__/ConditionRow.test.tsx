import type React from "react";
import { Text } from "react-native";
import renderer, { act } from "react-test-renderer";

import type { Suggestion } from "@/features/travel/api";
import { ConditionRow } from "@/features/travel/components/ConditionRow";

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

it("적용된 조건과 풀 수 있는 조건을 같이 보여준다", () => {
  const tree = draw(
    <ConditionRow applied={["실내", "한적"]} refinements={[loosen]} onRefine={jest.fn()} />,
  );

  expect(labels(tree)).toEqual(expect.arrayContaining(["실내", "한적", "실내 빼기"]));
});

it("조건을 좁히는 제안은 이 줄에 넣지 않는다", () => {
  const tree = draw(
    <ConditionRow applied={["제주"]} refinements={[tighten]} onRefine={jest.fn()} />,
  );

  expect(labels(tree)).not.toContain("한적한 곳으로");
});

it("풀기 칩을 누르면 그 축을 빼는 patch 가 나간다", () => {
  const onRefine = jest.fn();
  const tree = draw(<ConditionRow applied={["실내"]} refinements={[loosen]} onRefine={onRefine} />);

  const chip = tree.root.findAll(
    (node) => node.props.accessibilityLabel === "실내 빼기, 눌러서 조건 풀기",
  )[0];
  act(() => {
    chip.props.onPress();
  });

  expect(onRefine).toHaveBeenCalledWith({ drop: "indoor" });
});

it("보여줄 게 없으면 줄 자체를 그리지 않는다", () => {
  const tree = draw(<ConditionRow applied={[]} refinements={[tighten]} onRefine={jest.fn()} />);

  expect(tree.root.findAllByProps({ testID: "travel-conditions" })).toHaveLength(0);
});
