import { View, Pressable, Text, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { LoginCard } from "@/features/auth/components/LoginCard";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { colors, spacing } from "@/constants/theme";

export default function LoginScreen() {
  const insets = useSafeAreaInsets();
  const devLogin = useAuthStore((s) => s.devLogin);

  const close = () => {
    if (router.canGoBack()) router.back();
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={close} hitSlop={8}>
        <Icon name="chevron-left" size={24} />
      </Pressable>
      <LoginCard variant="full" onSuccess={close} />
      {__DEV__ ? (
        <Pressable
          style={[styles.dev, { bottom: insets.bottom + spacing.sm }]}
          onPress={() => {
            devLogin();
            close();
          }}
        >
          <Text style={styles.devText}>개발용 로그인 (DEV)</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  back: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  dev: { position: "absolute", alignSelf: "center" },
  devText: { color: colors.ter, fontSize: 12, fontWeight: "700", textDecorationLine: "underline" },
});
