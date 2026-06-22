import { View, Text, StyleSheet } from "react-native";
import { RemoteImage } from "@/components/RemoteImage";
import { Icon } from "@/components/Icon";
import type { User } from "@/lib/api-types";
import { colors, spacing } from "@/constants/theme";

export function ProfileHeader({ user }: { user: User }) {
  return (
    <View style={styles.row}>
      <View style={styles.avatar}>
        {user.avatarUrl ? (
          <RemoteImage uri={user.avatarUrl} style={styles.avatarImg} />
        ) : (
          <Icon name="person" size={30} color={colors.ter} />
        )}
      </View>
      <View>
        <Text style={styles.name}>{user.displayName ?? "여행자"}</Text>
        {user.email ? <Text style={styles.email}>{user.email}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: spacing.lg,
    backgroundColor: colors.bg,
  },
  avatar: {
    width: 62,
    height: 62,
    borderRadius: 31,
    overflow: "hidden",
    backgroundColor: colors.fill,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarImg: { width: "100%", height: "100%" },
  name: { fontSize: 19, fontWeight: "700", letterSpacing: -0.19, color: colors.ink },
  email: { color: colors.sec, fontSize: 13.5, marginTop: 3 },
});
