import { Appearance } from "react-native";
import * as SecureStore from "expo-secure-store";

const light = {
  bg: "#FFFFFF",
  inset: "#F7F7F8",
  skeleton: "#ECEDEF",
  ink: "#171719",
  sec: "rgba(55,56,60,0.61)",
  ter: "rgba(55,56,60,0.47)",
  line: "rgba(112,115,124,0.16)",
  fill: "rgba(112,115,124,0.05)",
  fillStrong: "rgba(112,115,124,0.09)",
  control: "rgba(12,14,18,0.35)",
  accent: "#FF3B53",
  accentText: "#E5334B",
  accentFill: "rgba(255,59,83,0.10)",
  scrim: "rgba(23,23,25,0.62)",
  glassFill: "rgba(255,255,255,0.85)",
  glassBorder: "rgba(112,115,124,0.22)",
  raise: "rgba(112,115,124,0.04)",
  raiseStrong: "#FFFFFF",
  onImage: "#FFFFFF",
  onDim: "rgba(255,255,255,0.85)",
  onLight: "#171719",
  danger: "#E5334B",
  positive: "#00BF40",
  caution: "#C77700",
  info: "#1B72E8",
} as const;

const dark = {
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

export type Palette = { [K in keyof typeof dark]: string };

const palettes: { light: Palette; dark: Palette } = { light, dark };

export type ThemeName = keyof typeof palettes;

const THEME_OVERRIDE_KEY = "theme_override";

function resolveThemeName(): ThemeName {
  let stored: string | null = null;
  try {
    stored = SecureStore.getItem(THEME_OVERRIDE_KEY);
  } catch {
    stored = null;
  }
  if (stored === "light" || stored === "dark") return stored;
  return Appearance.getColorScheme() === "dark" ? "dark" : "light";
}

export const themeName: ThemeName = resolveThemeName();

export async function setThemeOverride(name: ThemeName): Promise<void> {
  await SecureStore.setItemAsync(THEME_OVERRIDE_KEY, name);
}

export const colors: Palette = palettes[themeName];

export const darkColors: Palette = palettes.dark;

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
