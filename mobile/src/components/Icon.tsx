import type { ColorValue } from "react-native";
import Svg, { Path, Circle } from "react-native-svg";
import { colors } from "@/constants/theme";

export type IconName =
  | "chevron-left"
  | "chevron-right"
  | "chevron-down"
  | "share"
  | "heart"
  | "heart-fill"
  | "bookmark"
  | "bookmark-fill"
  | "clock"
  | "phone"
  | "globe"
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
  | "sparkle"
  | "log-in"
  | "log-out"
  | "shield-check"
  | "info";

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
  "chevron-down": { d: "M6 9l6 6 6-6" },
  share: { d: "M8.3 10.7l7.4-4.4M8.3 13.3l7.4 4.4" },
  heart: { d: "M12 20s-7-4.5-7-9.5A3.5 3.5 0 0 1 12 7a3.5 3.5 0 0 1 7 3.5C19 15.5 12 20 12 20z" },
  "heart-fill": {
    d: "M12 20s-7-4.5-7-9.5A3.5 3.5 0 0 1 12 7a3.5 3.5 0 0 1 7 3.5C19 15.5 12 20 12 20z",
    fill: true,
  },
  bookmark: { d: "M6 4h12v17l-6-4-6 4z" },
  "bookmark-fill": { d: "M6 4h12v17l-6-4-6 4z", fill: true },
  clock: { d: "M12 7v5l3 2" },
  phone: {
    d: "M5 4h4l2 5-3 2a13 13 0 0 0 6 6l2-3 5 2v4a1 1 0 0 1-1 1A17 17 0 0 1 4 5a1 1 0 0 1 1-1z",
  },
  globe: { d: "M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18" },
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
  "log-in": { d: "M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" },
  "log-out": { d: "M15 17l5-5-5-5M20 12H9M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3" },
  "shield-check": { d: "M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3zM9 12l2 2 4-4" },
  info: { d: "M12 11v5M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z" },
};

export function Icon({ name, size = 22, color = colors.ink, strokeWidth = 1.9 }: IconProps) {
  const spec = PATHS[name];
  const filled = spec.fill === true;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {name === "person" && (
        <Circle cx={12} cy={8} r={3.2} stroke={color} strokeWidth={strokeWidth} />
      )}
      {(name === "clock" || name === "globe") && (
        <Circle cx={12} cy={12} r={9} stroke={color} strokeWidth={strokeWidth} />
      )}
      {name === "share" && (
        <>
          <Circle cx={18} cy={5} r={2.6} stroke={color} strokeWidth={strokeWidth} />
          <Circle cx={6} cy={12} r={2.6} stroke={color} strokeWidth={strokeWidth} />
          <Circle cx={18} cy={19} r={2.6} stroke={color} strokeWidth={strokeWidth} />
        </>
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
