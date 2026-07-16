import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0e14",
        panel: "#0f141c",
        panel2: "#141b26",
        border: "#1e2733",
        muted: "#6b7785",
        fg: "#d7dee8",
        accent: "#22d3ee",
        pos: "#34d399",
        neg: "#f87171",
        warn: "#fbbf24",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 8px 24px -12px rgba(0,0,0,0.6)",
      },
    },
  },
  plugins: [],
};
export default config;
