import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#120A0E",          // page background
        coal: "#1A1216",         // surface
        coal2: "#241820",        // elevated surface
        coal3: "#2E1E28",        // hover surface
        wine: "#4A0E1F",         // brand burgundy
        winebright: "#6B1628",
        gold: "#D4A537",
        goldsoft: "#E9C878",
        golddim: "rgba(212,165,55,0.14)",
        cream: "#F5EBD8",
        sand: "#C9B8A6",
        muted: "#8F7F76",
        line: "rgba(245,235,216,0.09)",
      },
      fontFamily: {
        display: ["var(--font-anton)", "Impact", "sans-serif"],
        body: ["var(--font-inter)", "-apple-system", "sans-serif"],
        devanagari: ["'Noto Sans Devanagari'", "'Kohinoor Devanagari'", "'Devanagari Sangam MN'", "var(--font-anton)"],
      },
    },
  },
  plugins: [],
};
export default config;
