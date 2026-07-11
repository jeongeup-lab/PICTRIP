import { useEffect, useState } from "react";
import { View, Text, Pressable, Linking, StyleSheet } from "react-native";
import { Icon } from "@/components/Icon";
import { getPermissionStatus, type PermStatus } from "@/features/map/usecases/request-location";
import { APP_VERSION } from "@/lib/app-meta";
import { colors, spacing } from "@/constants/theme";

const PERM_LABEL: Record<PermStatus, string> = {
  granted: "허용됨",
  denied: "꺼짐",
  undetermined: "미설정",
};

export function SettingsRows({ onLogout }: { onLogout?: () => void }) {
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

      {onLogout ? (
        <Pressable style={styles.row} onPress={onLogout}>
          <View style={styles.icon}>
            <Icon name="log-out" size={21} color={colors.sec} />
          </View>
          <Text style={styles.label}>로그아웃</Text>
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
  icon: { width: 21, alignItems: "center" },
  label: { flex: 1, fontSize: 15.5, fontWeight: "600", color: colors.ink },
  value: { color: colors.ter, fontSize: 14 },
  permGranted: { fontSize: 13, fontWeight: "700", color: colors.accentText },
  permOff: { fontSize: 13, fontWeight: "700", color: colors.ter },
});
