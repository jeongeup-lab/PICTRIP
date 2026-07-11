import { useEffect, useState } from "react";
import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { getPermissionStatus, type PermStatus } from "@/features/map/usecases/request-location";
import { APP_VERSION } from "@/lib/app-meta";
import { colors, spacing } from "@/constants/theme";

const PERM_LABEL: Record<PermStatus, string> = {
  granted: "허용됨",
  denied: "꺼짐",
  undetermined: "미설정",
};

export function SettingsRows({
  onLogout,
  onDeleteAccount,
}: {
  onLogout?: () => void;
  onDeleteAccount?: () => void;
}) {
  const [perm, setPerm] = useState<PermStatus | null>(null);

  useEffect(() => {
    let active = true;
    void getPermissionStatus().then((s) => {
      if (active) setPerm(s);
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <View style={styles.group}>
      <Pressable style={[styles.row, styles.first]} onPress={() => Linking.openSettings()}>
        <View style={styles.icon}>
          <Icon name="map-pin" size={21} color={colors.sec} />
        </View>
        <Text style={styles.label}>위치 권한</Text>
        {perm ? (
          <Text style={perm === "granted" ? styles.permGranted : styles.permOff}>
            {PERM_LABEL[perm]}
          </Text>
        ) : null}
        <Icon name="chevron-right" size={20} color={colors.ter} />
      </Pressable>

      <View style={styles.row}>
        <View style={styles.icon}>
          <Icon name="info" size={21} color={colors.sec} />
        </View>
        <Text style={styles.label}>앱 버전</Text>
        <Text style={styles.value}>{APP_VERSION}</Text>
      </View>

      <Pressable style={styles.row} onPress={() => router.push("/legal")}>
        <View style={styles.icon}>
          <Icon name="shield-check" size={21} color={colors.sec} />
        </View>
        <Text style={styles.label}>약관·정책</Text>
        <Icon name="chevron-right" size={20} color={colors.ter} />
      </Pressable>

      {onLogout || onDeleteAccount ? <View style={styles.divider} /> : null}

      {onLogout ? (
        <Pressable style={[styles.row, styles.first]} onPress={onLogout}>
          <View style={styles.icon}>
            <Icon name="log-out" size={21} color={colors.sec} />
          </View>
          <Text style={styles.label}>로그아웃</Text>
        </Pressable>
      ) : null}

      {onDeleteAccount ? (
        <Pressable style={[styles.row, !onLogout && styles.first]} onPress={onDeleteAccount}>
          <View style={styles.icon}>
            <Icon name="person" size={21} color={colors.sec} />
          </View>
          <Text style={styles.label}>회원 탈퇴</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  group: { backgroundColor: colors.bg },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 13,
    paddingVertical: 16,
    paddingHorizontal: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  first: { borderTopWidth: 0 },
  divider: {
    height: 9,
    backgroundColor: colors.inset,
    borderTopWidth: 1,
    borderBottomWidth: 1,
    borderColor: colors.line,
  },
  icon: { width: 21, alignItems: "center" },
  label: { flex: 1, fontSize: 15.5, fontWeight: "600", color: colors.ink },
  value: { color: colors.ter, fontSize: 14 },
  permGranted: { fontSize: 13, fontWeight: "700", color: colors.accentText },
  permOff: { fontSize: 13, fontWeight: "700", color: colors.ter },
});
