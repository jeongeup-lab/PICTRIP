import { View, ScrollView, Linking, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { ScreenHeader } from "@/components/ScreenHeader";
import { ListGroup } from "@/components/ListGroup";
import { ListRow } from "@/components/ListRow";
import { useConsents } from "@/features/consent/queries";
import { useLocationConsentSync } from "@/features/consent/hooks/use-location-consent-sync";
import { PERM_LABEL, useAppPermissions } from "@/features/profile/hooks/use-app-permissions";
import type { PermStatus } from "@/features/map/usecases/request-location";
import { colors, spacing } from "@/constants/theme";

const permTone = (status: PermStatus | null) => (status === "granted" ? "on" : "off");
const permLabel = (status: PermStatus | null) => (status ? PERM_LABEL[status] : "확인 중");

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const { location, photos, camera } = useAppPermissions(true);
  const { data: consents } = useConsents();
  useLocationConsentSync(consents);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <ScreenHeader title="기기 권한" fallback="/(tabs)/profile" />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <ListGroup>
          <ListRow
            icon="map-pin"
            title="위치"
            value={permLabel(location)}
            tone={permTone(location)}
            chevron
            onPress={() => void Linking.openSettings()}
          />
          <ListRow
            icon="photo"
            title="사진"
            value={permLabel(photos)}
            tone={permTone(photos)}
            chevron
            onPress={() => void Linking.openSettings()}
          />
          <ListRow
            icon="camera"
            title="카메라"
            value={permLabel(camera)}
            tone={permTone(camera)}
            chevron
            onPress={() => void Linking.openSettings()}
          />
        </ListGroup>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  scroll: { paddingTop: spacing.md, paddingBottom: spacing.xxl },
});
