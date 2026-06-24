import { useEffect, useState } from "react";
import { Redirect } from "expo-router";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { getOnboardingSeen } from "@/lib/storage";
import { SplashScreen } from "@/components/SplashScreen";

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
    return <SplashScreen />;
  }
  return <Redirect href={target} />;
}
