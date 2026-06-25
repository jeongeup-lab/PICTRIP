import { QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Stack } from "expo-router";
import { queryClient } from "@/lib/query-client";
import { AuthPromptSheet } from "@/features/auth/components/AuthPromptSheet";

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="onboarding" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="curations/[slug]" />
          <Stack.Screen name="spots/[contentId]" />
          <Stack.Screen name="photo" options={{ presentation: "modal" }} />
          <Stack.Screen name="auth/login" options={{ presentation: "fullScreenModal" }} />
          <Stack.Screen name="auth/email" options={{ presentation: "fullScreenModal" }} />
          <Stack.Screen name="saved" />
          <Stack.Screen name="consent" />
          <Stack.Screen name="legal/index" />
          <Stack.Screen name="legal/[slug]" />
        </Stack>
        <AuthPromptSheet />
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}
