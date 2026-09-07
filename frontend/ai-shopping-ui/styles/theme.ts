export const T = {
  bg0: "#f7f7fb",
  bg1: "#ffffff",
  bg2: "#fbfbfe",
  bg3: "#f1f0f8",

  border: "rgba(24, 31, 70, 0.10)",
  borderHi: "rgba(255, 139, 77, 0.34)",

  accent: "#ff8b4d",
  accentDim: "rgba(255, 139, 77, 0.12)",
  indigo: "#7048ec",
  indigoDim: "rgba(112, 72, 236, 0.12)",

  pink: "#e96c98",
  pinkDim: "rgba(233, 108, 152, 0.14)",
  coral: "#ef6d68",
  coralDim: "rgba(239, 109, 104, 0.12)",
  sky: "#5f77e9",
  skyDim: "rgba(95, 119, 233, 0.13)",

  gold: "#f3ae44",
  goldDeep: "#e7962e",
  goldDim: "rgba(243, 174, 68, 0.16)",
  amber: "#f3bc4d",
  amberDim: "rgba(243, 188, 77, 0.14)",

  text0: "#171d41",
  text1: "#656a82",
  text2: "#9295a7",

  glass: "rgba(255, 255, 255, 0.78)",
  glassSolid: "#ffffff",

  shadow: "0 18px 50px rgba(52, 45, 101, 0.09)",
  shadowSoft: "0 8px 24px rgba(52, 45, 101, 0.08)",
  glow: "0 8px 24px rgba(255, 139, 77, 0.26)",

  display: "'Manrope', sans-serif",
  sans: "'Manrope', sans-serif",
  mono: "'JetBrains Mono', monospace",
} as const

export type ThemeTokens = typeof T
