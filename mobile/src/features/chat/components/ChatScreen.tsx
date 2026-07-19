import {
  View,
  Text,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { colors, spacing } from "@/constants/theme";
import { ChatComposer } from "@/features/chat/components/ChatComposer";
import { ChatThread } from "@/features/chat/components/ChatThread";
import { MoodGrid } from "@/features/chat/components/MoodGrid";
import { useChatStore } from "@/features/chat/stores/chat-store";

export function ChatScreen() {
  const store = useChatStore();
  const empty = store.entries.length === 0;

  const openSpot = (contentId: string) => router.push(`/spots/${contentId}`);
  const openMap = () => router.push("/map");
  const photoSoon = () =>
    Alert.alert(
      "사진으로 시작하기",
      "곧 열려요. 지금은 무드를 고르거나 직접 적어서 시작해 주세요.",
    );

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.topbar}>
        <Icon name="sparkle" size={18} color={colors.accentText} />
        <Text style={styles.title}>AI 발견</Text>
      </View>

      <KeyboardAvoidingView
        style={styles.body}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={90}
      >
        {empty ? (
          <ScrollView contentContainerStyle={styles.emptyWrap} keyboardShouldPersistTaps="handled">
            <View style={styles.greeting}>
              <View style={styles.sig}>
                <View style={styles.sigDot} />
                <Text style={styles.sigText}>픽트립 · 스무고개처럼 좁혀가요</Text>
              </View>
              <Text style={styles.greetTitle}>오늘은 어떤 결이 끌리세요?</Text>
              <Text style={styles.greetSub}>
                몇 번만 주고받으면 국내 여행지 중에서 딱 맞는 곳으로 좁혀드릴게요.
              </Text>
              <Text style={styles.greetLimit}>예약이나 일정 짜기는 못 해요.</Text>
            </View>
            <MoodGrid onPick={store.send} onPhoto={photoSoon} disabled={store.pending} />
          </ScrollView>
        ) : (
          <ChatThread
            entries={store.entries}
            phase={store.phase}
            pending={store.pending}
            onAnswer={store.pickAnswer}
            onRemoveCondition={store.removeCondition}
            onOpenSpot={openSpot}
            onMap={openMap}
            onRestart={store.reset}
          />
        )}

        <ChatComposer
          disabled={store.pending}
          placeholder={empty ? "예: 강릉 쪽 한적한 바다 카페" : "직접 적어도 돼요"}
          onSend={store.send}
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  topbar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  title: { fontSize: 17, fontWeight: "800", color: colors.ink, letterSpacing: -0.4 },
  body: { flex: 1 },
  emptyWrap: { padding: spacing.lg, gap: spacing.lg },
  greeting: { gap: 5, paddingTop: spacing.xs },
  sig: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 3 },
  sigDot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.accent },
  sigText: { fontSize: 12, fontWeight: "700", color: colors.accentText },
  greetTitle: { fontSize: 21, fontWeight: "800", color: colors.ink, letterSpacing: -0.4 },
  greetSub: { fontSize: 13.5, color: colors.sec, lineHeight: 19 },
  greetLimit: { fontSize: 11.5, color: colors.ter, marginTop: 2 },
});
