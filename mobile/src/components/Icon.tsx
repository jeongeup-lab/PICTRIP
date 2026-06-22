import type { ColorValue } from "react-native";
import Svg, { Path, Circle } from "react-native-svg";
import { colors } from "@/constants/theme";

export type IconName =
  | "chevron-left"
  | "chevron-right"
  | "share"
  | "heart"
  | "heart-fill"
  | "home"
  | "map-pin"
  | "camera"
  | "person"
  | "location"
  | "close"
  | "search"
  | "recenter"
  | "sort"
  | "image"
  | "sparkle";

interface IconProps {
  name: IconName;
  size?: number;
  color?: ColorValue;
  strokeWidth?: number;
}

// Each path drawn on a 24x24 viewBox, stroke = currentColor unless filled.
const PATHS: Record<IconName, { d?: string; fill?: boolean; extra?: "heart" }> = {
  "chevron-left": { d: "M15 5l-7 7 7 7" },
  "chevron-right": { d: "M9 5l7 7-7 7" },
  share: { d: "M12 3v12M12 3l-4 4M12 3l4 4M5 12v7h14v-7" },
  heart: { d: "M12 20s-7-4.5-7-9.5A3.5 3.5 0 0 1 12 7a3.5 3.5 0 0 1 7 3.5C19 15.5 12 20 12 20z" },
  "heart-fill": {
    d: "M12 20s-7-4.5-7-9.5A3.5 3.5 0 0 1 12 7a3.5 3.5 0 0 1 7 3.5C19 15.5 12 20 12 20z",
    fill: true,
  },
  home: { d: "M4 11l8-7 8 7M6 10v9h12v-9" },
  "map-pin": { d: "M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z" },
  camera: { d: "M4 8h3l2-2h6l2 2h3v11H4z" },
  person: { d: "M5 20a7 7 0 0 1 14 0" },
  location: {
    d: "M12 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z",
  },
  close: { d: "M6 6l12 12M18 6L6 18" },
  search: { d: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4" },
  recenter: { d: "M12 3v3M12 18v3M3 12h3M18 12h3" },
  sort: { d: "M4 7h16M7 12h10M10 17h4" },
  image: { d: "M3 5h18v14H3zM3 16l5-5 4 4 3-3 6 6" },
  sparkle: { d: "M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" },
};

export function Icon({ name, size = 22, color = colors.ink, strokeWidth = 1.9 }: IconProps) {
  const spec = PATHS[name];
  const filled = spec.fill === true;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {name === "person" && (
        <Circle cx={12} cy={8} r={3.2} stroke={color} strokeWidth={strokeWidth} />
      )}
      <Path
        d={spec.d}
        stroke={filled ? "none" : color}
        fill={filled ? color : "none"}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
