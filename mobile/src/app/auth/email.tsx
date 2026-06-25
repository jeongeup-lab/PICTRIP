import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { useAuthStore } from "@/features/auth/stores/auth-store";
import { AppError } from "@/lib/app-error";
import { colors, spacing } from "@/constants/theme";

type Mode = "login" | "signup";

function messageForError(err: unknown): string {
  if (err instanceof AppError) {
    // Branch on code only — never message (S01).
    switch (err.code) {
      case "EMAIL_TAKEN":
        return "이미 가입된 이메일이에요.";
      case "AUTH_INVALID_CREDENTIALS":
        return "이메일 또는 비밀번호가 올바르지 않아요.";
      case "VALIDATION_FAILED":
        return "이메일과 비밀번호(8자 이상)를 확인해 주세요.";
      case "NETWORK_ERROR":
        return "네트워크에 연결할 수 없어요.";
    }
  }
  return "잠시 후 다시 시도해 주세요.";
}

export default function EmailAuthScreen() {
  const insets = useSafeAreaInsets();
  const loginWithEmail = useAuthStore((s) => s.loginWithEmail);
  const signupWithEmail = useAuthStore((s) => s.signupWithEmail);

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    if (router.canGoBack()) router.back();
  };

  const isSignup = mode === "signup";
  const canSubmit = email.trim().length > 0 && password.length >= (isSignup ? 8 : 1) && !pending;

  const toggleMode = () => {
    setMode((m) => (m === "login" ? "signup" : "login"));
    setError(null);
  };

  const submit = async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      const trimmedEmail = email.trim();
      if (isSignup) {
        const trimmedName = name.trim();
        await signupWithEmail(trimmedEmail, password, trimmedName || undefined);
      } else {
        await loginWithEmail(trimmedEmail, password);
      }
      close();
    } catch (e) {
      setError(messageForError(e));
    } finally {
      setPending(false);
    }
  };

  return (
    <View style={styles.root}>
      <View style={{ paddingTop: insets.top + spacing.sm }}>
        <Pressable style={styles.back} onPress={close} hitSlop={8}>
          <Icon name="chevron-left" size={24} />
        </Pressable>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
          <Text style={styles.title}>{isSignup ? "회원가입" : "로그인"}</Text>
          <Text style={styles.subtitle}>
            {isSignup ? "이메일과 비밀번호로 가입해요." : "이메일과 비밀번호로 로그인해요."}
          </Text>

          {isSignup ? (
            <View style={styles.field}>
              <Text style={styles.label}>이름 (선택)</Text>
              <TextInput
                style={styles.input}
                value={name}
                onChangeText={setName}
                placeholder="이름"
                placeholderTextColor={colors.ter}
                autoCapitalize="none"
                autoComplete="name"
                returnKeyType="next"
                editable={!pending}
              />
            </View>
          ) : null}

          <View style={styles.field}>
            <Text style={styles.label}>이메일</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={colors.ter}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="email"
              textContentType="emailAddress"
              returnKeyType="next"
              editable={!pending}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>비밀번호</Text>
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder={isSignup ? "8자 이상" : "비밀번호"}
              placeholderTextColor={colors.ter}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete={isSignup ? "new-password" : "password"}
              textContentType={isSignup ? "newPassword" : "password"}
              returnKeyType="done"
              onSubmitEditing={() => {
                if (canSubmit) void submit();
              }}
              editable={!pending}
            />
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          <Pressable
            style={[styles.submit, !canSubmit && styles.submitDisabled]}
            onPress={submit}
            disabled={!canSubmit}
          >
            <Text style={styles.submitText}>
              {pending ? "처리 중…" : isSignup ? "회원가입" : "로그인"}
            </Text>
          </Pressable>

          <Pressable style={styles.toggle} onPress={toggleMode} disabled={pending} hitSlop={8}>
            <Text style={styles.toggleText}>
              {isSignup ? "이미 계정이 있어요 · " : "계정이 없어요 · "}
              <Text style={styles.toggleLink}>{isSignup ? "로그인" : "회원가입"}</Text>
            </Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  back: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  body: { paddingHorizontal: spacing.xl, paddingTop: spacing.lg, paddingBottom: spacing.xxl },
  title: { fontSize: 28, fontWeight: "800", letterSpacing: -0.84, color: colors.ink },
  subtitle: { fontSize: 15, color: colors.sec, marginTop: spacing.sm, marginBottom: spacing.xl },
  field: { marginBottom: spacing.lg },
  label: { fontSize: 13, fontWeight: "700", color: colors.sec, marginBottom: spacing.xs },
  input: {
    height: 54,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
    paddingHorizontal: spacing.md,
    fontSize: 16,
    color: colors.ink,
  },
  error: { color: colors.sec, fontSize: 13, marginBottom: spacing.md },
  submit: {
    height: 54,
    borderRadius: 13,
    backgroundColor: colors.ink,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.sm,
  },
  submitDisabled: { opacity: 0.4 },
  submitText: { color: colors.onImage, fontSize: 16, fontWeight: "700" },
  toggle: { alignSelf: "center", marginTop: spacing.xl, paddingVertical: spacing.sm },
  toggleText: { fontSize: 13, color: colors.ter },
  toggleLink: { color: colors.sec, fontWeight: "700", textDecorationLine: "underline" },
});
