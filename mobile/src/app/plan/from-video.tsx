import { useState } from "react";
import { Pressable, TextInput, View, Text, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { PlanNavBar } from "@/features/plan/components/PlanNavBar";
import { PlanLoading } from "@/features/plan/components/PlanLoading";
import { PlanToast } from "@/features/plan/components/PlanToast";
import { usePlanDraft } from "@/features/plan/stores/plan-draft-store";
import { useImportMutation } from "@/features/plan/queries";
import { planErrorMessage } from "@/features/plan/lib/plan-errors";
import { colors, radii, spacing } from "@/constants/theme";

export default function FromVideoScreen() {
  const [url, setUrl] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const startImportFlow = usePlanDraft((s) => s.startImportFlow);
  const importContent = useImportMutation();

  const submit = () => {
    const trimmed = url.trim();
    if (!trimmed) return;
    importContent.mutate(
      { url: trimmed },
      {
        onSuccess: (result) => {
          startImportFlow(result, trimmed);
          router.push("/plan/places");
        },
        onError: (error) => setToast(planErrorMessage(error)),
      },
    );
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <PlanNavBar title="영상으로 시작" onBack={() => router.back()} />

      {importContent.isPending ? (
        <PlanLoading
          title="영상 자막을 읽고 있어요"
          sub="장소 이름을 하나하나 찾는 중"
          slowSub="장소를 확인하는 중 — 수십 초 걸릴 수 있어요"
        />
      ) : (
        <View style={styles.body}>
          <Text style={styles.title}>봤던 그 여행,{"\n"}그대로 다녀오세요</Text>
          <Text style={styles.lead}>영상 속 장소를 모두 찾아 일정으로 만들어 드려요.</Text>

          <View style={styles.field}>
            <TextInput
              testID="plan-video-url"
              style={styles.input}
              value={url}
              onChangeText={setUrl}
              placeholder="유튜브 링크 붙여넣기"
              placeholderTextColor={colors.ter}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              returnKeyType="go"
              onSubmitEditing={submit}
            />
            <Pressable
              testID="plan-video-submit"
              style={[styles.submit, !url.trim() && styles.submitOff]}
              disabled={!url.trim()}
              onPress={submit}
            >
              <Text style={styles.submitText}>가져오기</Text>
            </Pressable>
          </View>

          <View style={styles.hint}>
            <Icon name="info" size={17} color={colors.ter} strokeWidth={1.8} />
            <Text style={styles.hintText}>자막 있는 영상이면 돼요 · 확인은 수십 초 걸려요</Text>
          </View>
        </View>
      )}

      <PlanToast message={toast} onHide={() => setToast(null)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  body: { paddingHorizontal: spacing.lg, paddingTop: spacing.xl },
  title: {
    fontSize: 21,
    lineHeight: 30,
    fontWeight: "800",
    letterSpacing: -0.5,
    color: colors.ink,
  },
  lead: { marginTop: 8, fontSize: 13.5, lineHeight: 20, color: colors.sec },
  field: {
    marginTop: 18,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radii.md,
    paddingLeft: 14,
    padding: 5,
  },
  input: { flex: 1, fontSize: 14, color: colors.ink, paddingVertical: 0 },
  submit: {
    height: 44,
    paddingHorizontal: 16,
    borderRadius: radii.md,
    backgroundColor: colors.ink,
    alignItems: "center",
    justifyContent: "center",
  },
  submitOff: { opacity: 0.4 },
  submitText: { fontSize: 14, fontWeight: "700", color: colors.onImage },
  hint: {
    marginTop: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    backgroundColor: colors.inset,
    borderRadius: radii.md,
    paddingVertical: 12,
    paddingHorizontal: 14,
  },
  hintText: { flex: 1, fontSize: 12, color: colors.sec },
});
