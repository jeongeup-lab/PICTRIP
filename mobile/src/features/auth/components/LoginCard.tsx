import { useState } from "react";
import { View, Text, Pressable, StyleSheet, Platform } from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { router } from "expo-router";
import { SocialButton } from "@/features/auth/components/SocialButton";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import type { Provider } from "@/features/auth/usecases/oauth-providers";
import { AppError } from "@/lib/app-error";
import { colors, spacing, radii } from "@/constants/theme";

interface Props {
  variant: "full" | "sheet";
  onSuccess: () => void;
  onCancel?: () => void;
  onEmailPress?: () => void;
}

const PROVIDERS: Provider[] = [
  "kakao",
  "google",
  ...(Platform.OS === "ios" ? (["apple"] as Provider[]) : []),
];

function BrandSymbol() {
  return (
    <View style={styles.sym}>
      <Svg
        width={46}
        height={46}
        viewBox="0 0 48 48"
        fill="none"
        stroke="#fff"
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <Circle cx={20} cy={10} r={3.6} />
        <Path d="M20 13.6 V28.5" />
        <Path d="M20 28.5 L15 40" />
        <Path d="M20 28.5 L25 40" />
        <Path d="M20 18 L26.5 15" />
        <Path d="M20 18.5 L15.5 24" />
        <Rect x={26} y={11.4} width={8} height={5.2} rx={1.6} fill="#fff" stroke="none" />
        <Circle cx={30} cy={14} r={1.3} fill={colors.bg} />
      </Svg>
      <View style={styles.symDot} />
    </View>
  );
}

export function LoginCard({ variant, onSuccess, onCancel, onEmailPress }: Props) {
  const loginWithOAuth = useAuthStore((s) => s.loginWithOAuth);
  const [pending, setPending] = useState<Provider | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handle = async (provider: Provider) => {
    if (pending) return;
    setPending(provider);
    setError(null);
    try {
      const res = await loginWithOAuth(provider);
      if (res === "success") onSuccess();
      else onCancel?.();
    } catch (e) {
      setError(e instanceof AppError ? e.message : "잠시 후 다시 시도해 주세요.");
    } finally {
      setPending(null);
    }
  };

  return (
    <View style={variant === "full" ? styles.full : styles.sheet}>
      {variant === "full" ? (
        <View style={styles.brand}>
          <BrandSymbol />
          <Text style={styles.word}>PicTrip</Text>
          <Text style={styles.tagline}>사진으로 떠나는 여행</Text>
        </View>
      ) : (
        <Text style={styles.sheetTitle}>저장하려면 로그인이 필요해요</Text>
      )}

      <View style={styles.social}>
        {PROVIDERS.map((p) => (
          <SocialButton
            key={p}
            provider={p}
            loading={pending === p}
            disabled={pending !== null && pending !== p}
            onPress={() => handle(p)}
          />
        ))}
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      {variant === "full" ? (
        <View style={styles.divider}>
          <View style={styles.dividerLine} />
          <Text style={styles.dividerText}>또는</Text>
          <View style={styles.dividerLine} />
        </View>
      ) : null}

      <View style={variant === "full" ? styles.emailWrap : styles.emailWrapSheet}>
        <Pressable
          style={({ pressed }) => [styles.emailBtn, pressed && styles.emailBtnPressed]}
          onPress={onEmailPress ?? (() => router.push("/auth/email"))}
          disabled={pending !== null}
        >
          <Text style={styles.emailBtnText}>이메일로 계속하기</Text>
        </Pressable>
      </View>

      <Text style={styles.terms}>
        계속 진행하면{" "}
        <Text style={styles.termsLink} onPress={() => router.push("/legal/terms")}>
          이용약관
        </Text>{" "}
        및{" "}
        <Text style={styles.termsLink} onPress={() => router.push("/legal/privacy")}>
          개인정보처리방침
        </Text>
        에{"\n"}동의하는 것으로 간주돼요.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  full: { flex: 1, justifyContent: "center", paddingBottom: spacing.xxl },
  sheet: { paddingTop: spacing.sm },
  brand: { alignItems: "center", marginBottom: spacing.xxl },
  sym: {
    width: 70,
    height: 70,
    borderRadius: 16,
    backgroundColor: colors.raiseStrong,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.lg,
  },
  symDot: {
    position: "absolute",
    right: -4,
    bottom: -4,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.accent,
    borderWidth: 3,
    borderColor: colors.bg,
  },
  word: { fontSize: 26, fontWeight: "800", letterSpacing: -0.8, color: colors.ink },
  tagline: { fontSize: 13.5, color: colors.sec, marginTop: spacing.xs },
  sheetTitle: {
    fontSize: 20,
    fontWeight: "800",
    letterSpacing: -0.4,
    color: colors.ink,
    textAlign: "center",
    marginBottom: spacing.lg,
  },
  social: { paddingHorizontal: spacing.lg, gap: 11 },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    marginTop: spacing.lg,
    gap: spacing.md,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: colors.line },
  dividerText: { fontSize: 11.5, color: colors.ter },
  emailWrap: { paddingHorizontal: spacing.lg, marginTop: spacing.lg },
  emailWrapSheet: { paddingHorizontal: spacing.lg, marginTop: 11 },
  emailBtn: {
    height: 52,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: "rgba(112,115,124,0.28)",
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
  },
  emailBtnPressed: { backgroundColor: colors.fill },
  emailBtnText: { fontSize: 16, fontWeight: "700", color: colors.ink },
  error: { color: colors.sec, fontSize: 13, textAlign: "center", marginTop: spacing.md },
  terms: {
    textAlign: "center",
    fontSize: 12,
    lineHeight: 19,
    color: colors.ter,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.lg,
  },
  termsLink: { color: colors.accentText, fontWeight: "700", textDecorationLine: "underline" },
});
