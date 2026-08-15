import { Pressable, StyleSheet, Text, View } from "react-native";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";

export type HomeScope = "nearby" | "national";

interface Props {
  scope: HomeScope;
  nearbyLabel: string;
  onChange: (scope: HomeScope) => void;
}

export function ScopeTabs({ scope, nearbyLabel, onChange }: Props) {
  return (
    <View style={styles.track}>
      <Tab
        testID="home-scope-nearby"
        icon="map-pin"
        label={nearbyLabel}
        active={scope === "nearby"}
        onPress={() => onChange("nearby")}
      />
      <Tab
        testID="home-scope-national"
        icon="flame"
        label="전국 인기"
        active={scope === "national"}
        onPress={() => onChange("national")}
      />
    </View>
  );
}

function Tab({
  testID,
  icon,
  label,
  active,
  onPress,
}: {
  testID: string;
  icon: "map-pin" | "flame";
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={[styles.tab, active && styles.tabActive]}
    >
      <Icon name={icon} size={16} color={active ? colors.accentText : colors.ter} />
      <Text style={[styles.label, active && styles.labelActive]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: "row",
    gap: 4,
    marginHorizontal: spacing.lg,
    padding: 4,
    borderRadius: 16,
    backgroundColor: colors.inset,
  },
  tab: {
    flex: 1,
    height: 46,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    borderRadius: 12,
  },
  tabActive: {
    backgroundColor: colors.raiseStrong,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  label: { fontSize: 14.5, fontWeight: "700", letterSpacing: -0.3, color: colors.ter },
  labelActive: { color: colors.ink, fontWeight: "800" },
});
