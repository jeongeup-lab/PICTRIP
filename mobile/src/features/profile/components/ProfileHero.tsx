import { View, Text, Pressable, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { User } from "@/lib/api-types";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  user: User;
  onPress: () => void;
}

function joinedLabel(createdAt: string | null): string | null {
  const date = createdAt?.slice(0, 10);
  return date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? `${date.replace(/-/g, ".")} 가입` : null;
}

export function ProfileHero({ user, onPress }: Props) {
  const joined = joinedLabel(user.createdAt);

  return (
    <Pressable
      accessibilityRole="button"
      style={styles.hero}
      onPress={onPress}
      testID="profile-hero"
    >
      <View style={styles.inner}>
        <View style={styles.avatar}>
          {user.avatarUrl ? (
            <RemoteImage uri={user.avatarUrl} style={styles.avatarImg} cropBanner={false} />
          ) : (
            <Icon name="person" size={26} color={colors.sec} />
          )}
        </View>
        <View style={styles.text}>
          <Text style={styles.name} numberOfLines={1}>
            {user.displayName ?? "여행자"}
          </Text>
          {user.email ? (
            <Text style={styles.email} numberOfLines={1}>
              {user.email}
            </Text>
          ) : null}
          {joined ? (
            <View style={styles.badge}>
              <Icon name="check" size={10} color={colors.ink} strokeWidth={2.6} />
              <Text style={styles.badgeText}>{joined}</Text>
            </View>
          ) : null}
        </View>
        <Icon name="chevron-right" size={18} color={colors.ter} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  hero: {
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    borderRadius: radii.lg + 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
    overflow: "hidden",
  },
  inner: { flexDirection: "row", alignItems: "center", gap: 13, padding: spacing.md + 2 },
  avatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    overflow: "hidden",
    backgroundColor: colors.fill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarImg: { width: "100%", height: "100%" },
  text: { flex: 1, minWidth: 0 },
  name: { fontSize: 18, fontWeight: "800", letterSpacing: -0.4, color: colors.ink },
  email: { marginTop: 3, fontSize: 12.5, color: colors.sec },
  badge: {
    marginTop: 8,
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.glassFill,
    paddingHorizontal: 9,
    paddingVertical: 3,
  },
  badgeText: { fontSize: 10.5, fontWeight: "800", letterSpacing: 0.2, color: colors.ink },
});
