import { useEffect, useState } from "react";
import { Redirect } from "expo-router";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { getOnboardingSeen } from "@/lib/storage";
import { SplashScreen } from "@/components/SplashScreen";

export default function BootGate() {
  const [target, setTarget] = useState<null | "/onboarding" | "/(tabs)">(null);
  const [minElapsed, setMinElapsed] = useState(false);

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

  // Keep the branded splash perceptibly visible on every cold start, even when
  // the async boot work resolves in well under a frame.
  useEffect(() => {
    const t = setTimeout(() => setMinElapsed(true), 1200);
    return () => clearTimeout(t);
  }, []);

  if (!target || !minElapsed) {
    return <SplashScreen />;
  }
  return <Redirect href={target} />;
}
