/**
 * Monochrome design tokens ported from docs/mockups/ CSS variables.
 * Ink/gray only — no rose, no color.
 */

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
  // On-image overlays
  scrim: "rgba(20,18,22,0.50)",
  scrimStrong: "rgba(16,14,18,0.64)",
  glassFill: "rgba(255,255,255,0.15)",
  glassBorder: "rgba(255,255,255,0.22)",
  onImage: "#FFFFFF",
  onDim: "rgba(255,255,255,0.85)",
} as const;

export const type = {
  family: undefined as undefined | string, // system default; Pretendard added later if bundled
  h1: { fontSize: 38, fontWeight: "800" as const, letterSpacing: -1 },
  h2: { fontSize: 25, fontWeight: "800" as const, letterSpacing: -0.5 },
  h3: { fontSize: 22, fontWeight: "800" as const, letterSpacing: -0.3 },
  hero: { fontSize: 30, fontWeight: "800" as const, letterSpacing: -0.6 },
  body: { fontSize: 15, fontWeight: "500" as const },
  bodyStrong: { fontSize: 15, fontWeight: "700" as const },
  caption: { fontSize: 13, fontWeight: "500" as const },
  eyebrow: { fontSize: 12, fontWeight: "800" as const, letterSpacing: 1.5 },
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
  sm: 12,
  md: 14,
  lg: 16,
  xl: 20,
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
