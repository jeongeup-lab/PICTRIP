import { type ReactNode } from "react";
import { ScrollView } from "react-native";

interface RailProps {
  children: ReactNode;
  gap?: number;
}

export function Rail({ children, gap = 12 }: RailProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ paddingHorizontal: 20, gap }}
    >
      {children}
    </ScrollView>
  );
}
