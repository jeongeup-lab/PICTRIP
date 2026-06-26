import { useEffect } from "react";
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
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const close = () => {
    if (router.canGoBack()) router.back();
    else router.replace("/(tabs)"); // deep-link / cold-start entry has nothing to pop
  };

  // Single source of dismissal: close once authenticated by any path (OAuth, dev
  // login, or already-authed re-entry). The email entry replaces this screen
  // (see onEmailPress) so the two auth modals never stack — only one effect ever
  // fires a back().
  useEffect(() => {
    if (isAuthenticated) close();
  }, [isAuthenticated]);

  return (
    <View style={[styles.root, { paddingTop: insets.top + spacing.sm }]}>
      <Pressable style={styles.back} onPress={close} hitSlop={8}>
        <Icon name="chevron-left" size={24} />
      </Pressable>
      <LoginCard
        variant="full"
        onSuccess={() => {}}
        onEmailPress={() => router.replace("/auth/email")}
      />
      {__DEV__ ? (
        <Pressable
          style={[styles.dev, { bottom: insets.bottom + spacing.sm }]}
          onPress={() => devLogin()}
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
