export const colors = {
  bg: "#FFFFFF",
  inset: "#F7F7F8",
  skeleton: "#ECEDEF",
  ink: "#171719",
  sec: "#5A5C63",
  ter: "#9396A0",
  line: "rgba(112,115,124,0.18)",
  fill: "rgba(112,115,124,0.08)",
  fillStrong: "rgba(112,115,124,0.10)",
  control: "rgba(23,23,25,0.34)",
  accent: "#03C75A",
  accentText: "#03A94E",
  accentFill: "rgba(3,199,90,0.08)",
  scrim: "rgba(20,18,22,0.50)",
  glassFill: "rgba(255,255,255,0.15)",
  glassBorder: "rgba(255,255,255,0.22)",
  onImage: "#FFFFFF",
  onDim: "rgba(255,255,255,0.85)",
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
    shadowColor: "#171719",
    shadowOpacity: 0.12,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 4,
  },
  fab: {
    shadowColor: "#100E12",
    shadowOpacity: 0.18,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
} as const;
