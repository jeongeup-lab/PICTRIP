import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { Icon } from "@/components/Icon";
import { colors } from "@/constants/theme";
import { styles } from "@/features/home/components/taste-picker-styles";

const BG = "#141216";
const MIN_SAVES = 3;

export function TastePickerState({
  text,
  loading,
  onClose,
}: {
  readonly text: string;
  readonly loading?: boolean;
  readonly onClose?: () => void;
}) {
  return (
    <View style={[styles.root, styles.centered]}>
      {loading ? <ActivityIndicator color={colors.onImage} /> : null}
      <Text style={styles.muted}>{text}</Text>
      {onClose ? (
        <Pressable testID="taste-close" onPress={onClose} style={styles.finishButton}>
          <Text style={styles.finishText}>돌아가기</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function TastePickerCompletion({
  enoughSaves,
  onClose,
}: {
  readonly enoughSaves: boolean;
  readonly onClose: () => void;
}) {
  return (
    <View style={styles.centered}>
      <Icon name="sparkle" size={34} color={colors.accentText} />
      <Text style={styles.doneTitle}>
        {enoughSaves ? "취향을 다 읽었어요" : "조금 더 저장해 볼까요?"}
      </Text>
      <Text style={styles.muted}>
        {enoughSaves
          ? "홈에서 추천 장소를 확인해 보세요."
          : `${MIN_SAVES}곳 이상 저장하면 추천이 시작돼요.`}
      </Text>
      <Pressable testID="taste-finish" onPress={onClose} style={styles.finishButton}>
        <Text style={styles.finishText}>홈으로 돌아가기</Text>
      </Pressable>
    </View>
  );
}

export function TastePickerScrim() {
  return (
    <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
      <Defs>
        <LinearGradient id="tasteScrim" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0.4" stopColor={BG} stopOpacity={0} />
          <Stop offset="1" stopColor={BG} stopOpacity={0.85} />
        </LinearGradient>
      </Defs>
      <Rect x="0" y="0" width="100%" height="100%" fill="url(#tasteScrim)" />
    </Svg>
  );
}
