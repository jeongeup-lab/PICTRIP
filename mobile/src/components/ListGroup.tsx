import { Children, Fragment, type ReactNode } from "react";
import { View, StyleSheet, type StyleProp, type ViewStyle } from "react-native";
import { colors, radii, spacing } from "@/constants/theme";

interface Props {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}

export function ListGroup({ children, style }: Props) {
  const rows = Children.toArray(children).filter(Boolean);
  return (
    <View style={[styles.group, style]}>
      {rows.map((row, index) => (
        <Fragment key={index}>
          {index > 0 ? <View style={styles.divider} /> : null}
          {row}
        </Fragment>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  group: {
    marginHorizontal: spacing.md,
    borderRadius: radii.lg + 4,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.raise,
    overflow: "hidden",
  },
  divider: { height: 1, marginLeft: 52, backgroundColor: colors.line },
});
