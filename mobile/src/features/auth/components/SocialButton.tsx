import { Pressable, Text, View, ActivityIndicator, StyleSheet } from "react-native";
import Svg, { Path } from "react-native-svg";
import type { Provider } from "@/features/auth/usecases/oauth-providers";
import { colors } from "@/constants/theme";

interface Props {
  provider: Provider;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
}

const LABEL: Record<Provider, string> = {
  kakao: "카카오로 계속하기",
  google: "Google로 계속하기",
  apple: "Apple로 계속하기",
};

// Brand colors are the documented exception to the monochrome rule (mockup 03).
const STYLE: Record<Provider, { bg: string; fg: string; border?: string }> = {
  kakao: { bg: "#FEE500", fg: "#181600" },
  google: { bg: "#FFFFFF", fg: colors.ink, border: colors.line },
  apple: { bg: "#111113", fg: "#FFFFFF" },
};

function ProviderGlyph({ provider, color }: { provider: Provider; color: string }) {
  if (provider === "kakao") {
    return (
      <Svg width={20} height={20} viewBox="0 0 24 24" fill={color}>
        <Path d="M12 3C6.9 3 2.8 6.2 2.8 10.2c0 2.6 1.8 4.9 4.4 6.2-.2.7-.7 2.5-.8 2.9 0 .2.1.4.4.2.2-.1 2.6-1.8 3.7-2.5.5.1 1 .1 1.5.1 5.1 0 9.2-3.2 9.2-7.2S17.1 3 12 3z" />
      </Svg>
    );
  }
  if (provider === "apple") {
    return (
      <Svg width={20} height={20} viewBox="0 0 24 24" fill={color}>
        <Path d="M16.4 12.8c0-2.2 1.8-3.3 1.9-3.4-1-1.5-2.6-1.7-3.2-1.7-1.4-.1-2.6.8-3.3.8-.7 0-1.7-.8-2.8-.8-1.5 0-2.8.8-3.6 2.2-1.5 2.7-.4 6.6 1.1 8.8.7 1 1.6 2.2 2.7 2.2 1.1 0 1.5-.7 2.8-.7s1.6.7 2.8.7c1.2 0 1.9-1.1 2.6-2.1.8-1.2 1.2-2.3 1.2-2.4-.1 0-2.3-.9-2.3-3.6zM14.3 6.1c.6-.7 1-1.7.9-2.7-.9 0-1.9.6-2.5 1.3-.5.6-1 1.6-.9 2.6 1 0 2-.5 2.5-1.2z" />
      </Svg>
    );
  }
  return (
    <Svg width={20} height={20} viewBox="0 0 24 24">
      <Path
        fill="#4285F4"
        d="M22.5 12.2c0-.7-.06-1.4-.18-2.05H12v3.88h5.9a5.05 5.05 0 0 1-2.19 3.31v2.75h3.54c2.07-1.9 3.25-4.7 3.25-7.89Z"
      />
      <Path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.54-2.75c-.98.66-2.23 1.05-3.74 1.05-2.87 0-5.3-1.94-6.17-4.55H2.18v2.84A11 11 0 0 0 12 23Z"
      />
      <Path
        fill="#FBBC05"
        d="M5.83 14.09a6.6 6.6 0 0 1 0-4.18V7.07H2.18a11 11 0 0 0 0 9.86l3.65-2.84Z"
      />
      <Path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.14-3.14C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07l3.65 2.84C6.7 7.3 9.13 5.38 12 5.38Z"
      />
    </Svg>
  );
}

export function SocialButton({ provider, onPress, loading, disabled }: Props) {
  const s = STYLE[provider];
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={[
        styles.btn,
        { backgroundColor: s.bg },
        s.border ? { borderWidth: 1, borderColor: s.border } : null,
        (disabled || loading) && styles.dim,
      ]}
    >
      <View style={styles.glyph}>
        {loading ? (
          <ActivityIndicator color={s.fg} />
        ) : (
          <ProviderGlyph provider={provider} color={s.fg} />
        )}
      </View>
      <Text style={[styles.label, { color: s.fg }]}>{LABEL[provider]}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    height: 54,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
  },
  glyph: { position: "absolute", left: 18 },
  label: { fontSize: 16, fontWeight: "700" },
  dim: { opacity: 0.6 },
});
