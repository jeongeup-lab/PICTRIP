import { useEffect, useState } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { Redirect } from "expo-router";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { getOnboardingSeen } from "@/lib/storage";
import { colors } from "@/constants/theme";

export default function BootGate() {
  const [target, setTarget] = useState<null | "/onboarding" | "/(tabs)">(null);

  useEffect(() => {
    let active = true;
    (async () => {
      const [seen] = await Promise.all([getOnboardingSeen(), useAuthStore.getState().hydrate()]);
      if (active) setTarget(seen ? "/(tabs)" : "/onboarding");
    })();
    return () => {
      active = false;
    };
  }, []);

  if (!target) {
    return (
      <View style={styles.splash}>
        <ActivityIndicator color={colors.ink} />
      </View>
    );
  }
  return <Redirect href={target} />;
}

const styles = StyleSheet.create({
  splash: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
});
