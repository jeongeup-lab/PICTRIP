import { View, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ExploreGrid } from "@/features/explore/components/ExploreGrid";
import { colors } from "@/constants/theme";

export default function ExploreScreen() {
  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.body}>
        <ExploreGrid />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.ink },
  body: { flex: 1 },
});
