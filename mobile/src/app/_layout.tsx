import { useEffect } from "react";
import { AppState, StatusBar } from "react-native";
import { QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider, initialWindowMetrics } from "react-native-safe-area-context";
import { Stack } from "expo-router";
import { queryClient } from "@/lib/query-client";
import { warmConnection } from "@/lib/warm-connection";
import { applyPendingUpdate } from "@/lib/ota";
import { AuthPromptSheet } from "@/features/auth/components/AuthPromptSheet";
import { colors } from "@/constants/theme";

export default function RootLayout() {
  useEffect(() => {
    warmConnection();
    void applyPendingUpdate();
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "active") return;
      warmConnection();
      void applyPendingUpdate();
    });
    return () => sub.remove();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider initialMetrics={initialWindowMetrics}>
        <StatusBar barStyle="light-content" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: colors.bg },
          }}
        >
          <Stack.Screen name="index" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="spots/[contentId]" />
          <Stack.Screen
            name="channels"
            options={{ presentation: "fullScreenModal", headerShown: false }}
          />
          <Stack.Screen
            name="taste"
            options={{ presentation: "fullScreenModal", headerShown: false }}
          />
          <Stack.Screen name="auth/login" options={{ presentation: "fullScreenModal" }} />
          <Stack.Screen name="saved" />
          <Stack.Screen name="settings" />
          <Stack.Screen name="account" />
          <Stack.Screen
            name="account/delete"
            options={{ presentation: "fullScreenModal", headerShown: false }}
          />
          <Stack.Screen name="consent" />
          <Stack.Screen name="legal/index" />
          <Stack.Screen name="legal/[slug]" />
        </Stack>
        <AuthPromptSheet />
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
