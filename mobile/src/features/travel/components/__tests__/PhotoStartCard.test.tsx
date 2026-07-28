import renderer, { act } from "react-test-renderer";
import { PhotoStartCard } from "@/features/travel/components/PhotoStartCard";

function render(onPress: () => void) {
  let tree: renderer.ReactTestRenderer;
  act(() => {
    tree = renderer.create(<PhotoStartCard onPress={onPress} />);
  });
  return tree!;
}

function findByTestID(tree: renderer.ReactTestRenderer, id: string) {
  return tree.root.findAll((n) => n.props?.testID === id)[0];
}

it("짧은 제목과 한 줄 설명만 보여준다", () => {
  const tree = render(jest.fn());

  const text = JSON.stringify(tree.toJSON());
  expect(text).toContain("사진으로 찾기");
  expect(text).toContain("닮은 곳을 찾아드려요");
  expect(text).not.toContain("서버에 저장하지 않고 비교 후 폐기해요");
});

it("탭하면 onPress를 부른다", () => {
  const onPress = jest.fn();
  const tree = render(onPress);

  act(() => {
    findByTestID(tree, "travel-photo-start").props.onPress();
  });

  expect(onPress).toHaveBeenCalledTimes(1);
});
