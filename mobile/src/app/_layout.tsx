import { useEffect } from "react";
import { AppState } from "react-native";
import { QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider, initialWindowMetrics } from "react-native-safe-area-context";
import { Stack } from "expo-router";
import { queryClient } from "@/lib/query-client";
import { warmConnection } from "@/lib/warm-connection";
import { AuthPromptSheet } from "@/features/auth/components/AuthPromptSheet";

export default function RootLayout() {
  useEffect(() => {
    warmConnection();
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") warmConnection();
    });
    return () => sub.remove();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider initialMetrics={initialWindowMetrics}>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="spots/[contentId]" />
          <Stack.Screen
            name="channels"
            options={{ presentation: "fullScreenModal", headerShown: false }}
          />
          <Stack.Screen name="auth/login" options={{ presentation: "fullScreenModal" }} />
          <Stack.Screen name="auth/email" options={{ presentation: "fullScreenModal" }} />
          <Stack.Screen name="saved" />
          <Stack.Screen name="map" />
          <Stack.Screen name="settings" />
          <Stack.Screen name="account" />
          <Stack.Screen name="consent" />
          <Stack.Screen name="legal/index" />
          <Stack.Screen name="legal/[slug]" />
        </Stack>
        <AuthPromptSheet />
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
