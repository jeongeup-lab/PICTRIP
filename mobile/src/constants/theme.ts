export const colors = {
  bg: "#14161A",
  inset: "#1A1D22",
  skeleton: "#22262C",
  ink: "#F4F5F7",
  sec: "rgba(235,238,245,0.62)",
  ter: "rgba(235,238,245,0.34)",
  line: "rgba(255,255,255,0.11)",
  fill: "rgba(255,255,255,0.06)",
  fillStrong: "rgba(255,255,255,0.10)",
  control: "rgba(12,14,18,0.55)",
  accent: "#FF3B53",
  accentText: "#FF8494",
  accentFill: "rgba(255,59,83,0.18)",
  scrim: "rgba(6,8,12,0.55)",
  glassFill: "rgba(30,33,39,0.72)",
  glassBorder: "rgba(255,255,255,0.16)",
  raise: "rgba(255,255,255,0.05)",
  raiseStrong: "rgba(48,52,60,0.60)",
  onImage: "#FFFFFF",
  onDim: "rgba(255,255,255,0.85)",
  onLight: "#171719",
  danger: "#FF3B53",
  positive: "#6FDC8C",
  caution: "#FFC46B",
  info: "#4A9EFF",
} as const;

export const mapTones = {
  land: "#23262C",
  water: "#0B3042",
  coast: "#155069",
  road: "#32373F",
  roadTop: "#4D545E",
  label: "#7B838F",
} as const;

export const spacing = {
  xs: 6,
  sm: 10,
  md: 14,
  lg: 20,
  xl: 24,
  xxl: 32,
} as const;

export const radii = {
  sm: 6,
  md: 8,
  lg: 12,
  xl: 12,
  pill: 999,
} as const;

export const shadows = {
  card: {
    shadowColor: "#000000",
    shadowOpacity: 0.55,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 4,
  },
  fab: {
    shadowColor: "#000000",
    shadowOpacity: 0.7,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
  sheet: {
    shadowColor: "#000000",
    shadowOpacity: 0.85,
    shadowRadius: 50,
    shadowOffset: { width: 0, height: -18 },
    elevation: 12,
  },
} as const;
