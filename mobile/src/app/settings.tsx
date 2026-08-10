import { View, Text, Pressable, ScrollView, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Icon } from "@/components/Icon";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { SectionTitle } from "@/components/SectionTitle";
import { PERM_LABEL, useAppPermissions } from "@/features/profile/hooks/use-app-permissions";
import type { PermStatus } from "@/features/map/usecases/request-location";
import { APP_BUILD_LABEL } from "@/lib/app-meta";
import { colors, spacing } from "@/constants/theme";

export const PHOTO_NOTICE =
  "사진으로 찾기에 올린 이미지는 서버에 저장하지 않고 분석 직후 폐기해요.";

const permTone = (status: PermStatus | null) => (status === "granted" ? "on" : "off");

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const { location, photos, camera } = useAppPermissions(true);

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
        <Text style={styles.note}>{PHOTO_NOTICE}</Text>

        <SectionTitle title="앱" />
        <ListGroup>
          <ListRow
            icon="shield-check"
            title="약관·정책"
            chevron
            onPress={() => router.push("/legal")}
          />
          <ListRow icon="info" title="앱 버전" value={APP_BUILD_LABEL} />
        </ListGroup>
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
});
