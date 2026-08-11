import { Pressable, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { useSaveOptimistic } from "@/features/saved/hooks/use-save-optimistic";
import { colors } from "@/constants/theme";

interface Props {
  contentId: string;
  size?: number;
}

export function SaveStar({ contentId, size = 24 }: Props) {
  const { saved, toggle } = useSaveOptimistic(contentId);
  return (
    <Pressable
      testID="home-save-star"
      accessibilityRole="button"
      accessibilityLabel={saved ? "저장 해제" : "저장"}
      hitSlop={10}
      onPress={() => void toggle()}
      style={styles.button}
    >
      <Icon
        name={saved ? "star-fill" : "star"}
        size={size}
        color={saved ? colors.accent : colors.ter}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: { alignItems: "center", justifyContent: "center" },
});
