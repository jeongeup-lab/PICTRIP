import { useEffect } from "react";
import {
  View,
  Text,
  Pressable,
  ScrollView,
  Switch,
  Share,
  Linking,
  StyleSheet,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { SectionTitle } from "@/components/SectionTitle";
import { useSavedList } from "@/features/saved/queries";
import { buildSavedCsv } from "@/features/saved/lib/export-csv";
import { PERM_LABEL, useAppPermissions } from "@/features/profile/hooks/use-app-permissions";
import { useNotificationPrefs } from "@/features/profile/stores/notification-prefs-store";
import { NOTIFICATION_TOPICS } from "@/features/profile/lib/notification-prefs";
import type { PermStatus } from "@/features/map/usecases/request-location";
import { APP_VERSION } from "@/lib/app-meta";
import { colors, spacing } from "@/constants/theme";

export const PHOTO_NOTICE =
  "사진으로 찾기에 올린 이미지는 서버에 저장하지 않고 분석 직후 폐기해요.";
export const PUSH_NOTICE = "알림 발송은 준비 중이에요. 지금은 이 기기에만 저장돼요.";

const permTone = (status: PermStatus | null) => (status === "granted" ? "on" : "off");

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const { location, photos, camera } = useAppPermissions(true);
  const { data: saved } = useSavedList();
  const prefs = useNotificationPrefs((s) => s.prefs);
  const toggle = useNotificationPrefs((s) => s.toggle);
  const hydrate = useNotificationPrefs((s) => s.hydrate);
  const scraps = saved ?? [];

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  const exportCsv = () => {
    if (scraps.length === 0) return;
    void Share.share({ message: buildSavedCsv(scraps) });
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <View style={styles.nav}>
        <Pressable style={styles.navBtn} onPress={() => router.back()} hitSlop={8}>
          <Icon name="chevron-left" size={23} />
        </Pressable>
        <Text style={styles.title}>설정</Text>
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <SectionTitle title="권한" />
        <ListGroup>
          <ListRow
            icon="map-pin"
            title="위치"
            sub="내 근처 검색 · 거리 계산"
            value={location ? PERM_LABEL[location] : null}
            tone={permTone(location)}
            chevron
            onPress={() => void Linking.openSettings()}
          />
          <ListRow
            icon="photo"
            title="사진"
            sub="사진으로 찾기"
            value={photos ? PERM_LABEL[photos] : null}
            tone={permTone(photos)}
            chevron
            onPress={() => void Linking.openSettings()}
          />
          <ListRow
            icon="camera"
            title="카메라"
            sub="바로 찍어서 찾기"
            value={camera ? PERM_LABEL[camera] : null}
            tone={permTone(camera)}
            chevron
            onPress={() => void Linking.openSettings()}
          />
        </ListGroup>

        <SectionTitle title="알림" />
        <ListGroup>
          {NOTIFICATION_TOPICS.map((topic) => (
            <ListRow
              key={topic.topic}
              title={topic.title}
              sub={topic.sub}
              right={
                <Switch
                  value={prefs[topic.topic]}
                  onValueChange={(next) => toggle(topic.topic, next)}
                  trackColor={{ false: colors.line, true: colors.accent }}
                  testID={`notify-${topic.topic}`}
                />
              }
            />
          ))}
        </ListGroup>
        <Text style={styles.note}>{PUSH_NOTICE}</Text>

        {scraps.length > 0 ? (
          <>
            <SectionTitle title="내 데이터" />
            <ListGroup>
              <ListRow
                icon="download"
                title="스크랩 내보내기"
                sub={`${scraps.length}곳 · CSV`}
                chevron
                onPress={exportCsv}
                testID="export-saved"
              />
            </ListGroup>
          </>
        ) : null}
        <Text style={styles.note}>{PHOTO_NOTICE}</Text>

        <SectionTitle title="앱" />
        <ListGroup>
          <ListRow
            icon="shield-check"
            title="약관·정책"
            chevron
            onPress={() => router.push("/legal")}
          />
          <ListRow icon="info" title="앱 버전" value={APP_VERSION} />
        </ListGroup>

        <Text style={styles.foot}>관광 정보 출처 · 한국관광공사 TourAPI</Text>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  nav: {
    height: 50,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  navBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  title: {
    position: "absolute",
    left: 0,
    right: 0,
    textAlign: "center",
    fontSize: 17,
    fontWeight: "700",
    color: colors.ink,
  },
  scroll: { paddingBottom: spacing.xxl },
  note: {
    marginTop: 10,
    paddingHorizontal: spacing.lg,
    fontSize: 11.5,
    lineHeight: 17,
    color: colors.ter,
  },
  foot: {
    marginTop: spacing.lg,
    paddingHorizontal: spacing.lg,
    fontSize: 11.5,
    color: colors.ter,
  },
});
