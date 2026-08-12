import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { colors } from "@/constants/theme";

interface Props {
  contentId: string;
  size?: number;
  testID?: string;
  color?: string;
  activeColor?: string;
  style?: StyleProp<ViewStyle>;
  onToggled?: (saved: boolean) => void;
}

export function SaveButton({
  contentId,
  size = 24,
  testID = "save-button",
  color = colors.ter,
  activeColor = colors.accent,
  style,
  onToggled,
}: Props) {
  const { saved, toggle } = useSaveOptimistic(contentId);
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={saved ? "스크랩 해제" : "스크랩"}
      accessibilityState={{ selected: saved }}
      hitSlop={10}
      onPress={() => {
        void toggle().then((next) => {
          if (next !== null) onToggled?.(next);
        });
      }}
      style={[styles.button, style]}
    >
      <Icon
        name={saved ? "bookmark-fill" : "bookmark"}
        size={size}
        color={saved ? activeColor : color}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: { alignItems: "center", justifyContent: "center" },
});
