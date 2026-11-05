import { loadFont } from "@remotion/google-fonts/NotoSansThai";

export const { fontFamily } = loadFont("normal", {
  weights: ["400", "700"],
  subsets: ["thai", "latin"],
});

export const C = {
  bg: "#0b1220",
  panel: "#131d33",
  line: "#2a3a5c",
  text: "#f2f5fb",
  dim: "#9fb0cf",
  teal: "#3dd6c0",
  amber: "#ffb84d",
  red: "#ff6b6b",
  blue: "#6aa8ff",
};
