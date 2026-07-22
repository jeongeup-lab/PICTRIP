import type { ColorValue } from "react-native";
import Svg, { Path, Circle, Rect } from "react-native-svg";
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
  | "info"
  | "photo"
  | "video"
  | "check"
  | "calendar"
  | "swap"
  | "trash"
  | "arrow-down";

interface IconProps {
  name: IconName;
  size?: number;
  color?: ColorValue;
  strokeWidth?: number;
}

interface IconSpec {
  d?: string;
  fill?: boolean;
  circles?: { cx: number; cy: number; r: number }[];
  rects?: { x: number; y: number; width: number; height: number; rx: number }[];
}

const PATHS: Record<IconName, IconSpec> = {
  "chevron-left": { d: "M15 5l-7 7 7 7" },
  "chevron-right": { d: "M9 5l7 7-7 7" },
  "chevron-down": { d: "M6 9l6 6 6-6" },
  share: {
    d: "M8.3 10.7l7.4-4.4M8.3 13.3l7.4 4.4",
    circles: [
      { cx: 18, cy: 5, r: 2.6 },
      { cx: 6, cy: 12, r: 2.6 },
      { cx: 18, cy: 19, r: 2.6 },
    ],
  },
  heart: { d: "M12 20s-7-4.5-7-9.5A3.5 3.5 0 0 1 12 7a3.5 3.5 0 0 1 7 3.5C19 15.5 12 20 12 20z" },
  "heart-fill": {
    d: "M12 20s-7-4.5-7-9.5A3.5 3.5 0 0 1 12 7a3.5 3.5 0 0 1 7 3.5C19 15.5 12 20 12 20z",
    fill: true,
  },
  bookmark: { d: "M6 4h12v17l-6-4-6 4z" },
  "bookmark-fill": { d: "M6 4h12v17l-6-4-6 4z", fill: true },
  clock: { d: "M12 7v5l3 2", circles: [{ cx: 12, cy: 12, r: 9 }] },
  phone: {
    d: "M5 4h4l2 5-3 2a13 13 0 0 0 6 6l2-3 5 2v4a1 1 0 0 1-1 1A17 17 0 0 1 4 5a1 1 0 0 1 1-1z",
  },
  globe: {
    d: "M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18",
    circles: [{ cx: 12, cy: 12, r: 9 }],
  },
  home: { d: "M4 11l8-7 8 7M6 10v9h12v-9" },
  "map-pin": { d: "M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11z" },
  camera: { d: "M4 8h3l2-2h6l2 2h3v11H4z" },
  person: { d: "M5 20a7 7 0 0 1 14 0", circles: [{ cx: 12, cy: 8, r: 3.2 }] },
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
  photo: {
    d: "M3.5 16.5l4.8-4.6 4 3.8 3-2.8 5.2 4.6",
    rects: [{ x: 3, y: 5, width: 18, height: 14, rx: 2.5 }],
    circles: [{ cx: 9, cy: 10.2, r: 1.8 }],
  },
  video: {
    d: "M10.2 9.3v5.4l4.8-2.7z",
    rects: [{ x: 3, y: 5, width: 18, height: 14, rx: 3.5 }],
  },
  check: { d: "M4.5 12.5l4.6 4.6L19.5 6.7" },
  calendar: {
    d: "M4 10.5h16M8.5 4v4M15.5 4v4",
    rects: [{ x: 4, y: 6, width: 16, height: 14, rx: 2 }],
  },
  swap: { d: "M4 7h13M14 3.5L17.5 7 14 10.5M20 17H7M10 13.5L6.5 17l3.5 3.5" },
  trash: { d: "M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13M10 11v6M14 11v6" },
  "arrow-down": { d: "M12 4v16M8 16l4 4 4-4" },
};

export function Icon({ name, size = 22, color = colors.ink, strokeWidth = 1.9 }: IconProps) {
  const spec = PATHS[name];
  const filled = spec.fill === true;
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {spec.rects?.map((r) => (
        <Rect key={`${r.x}-${r.y}`} {...r} stroke={color} strokeWidth={strokeWidth} />
      ))}
      {spec.circles?.map((c) => (
        <Circle key={`${c.cx}-${c.cy}`} {...c} stroke={color} strokeWidth={strokeWidth} />
      ))}
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
