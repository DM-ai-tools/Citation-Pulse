import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07130D",
          900: "#0D2118",
          800: "#163126",
          700: "#204236",
        },
        brand: {
          primary: "#1FB36B",
          primaryBright: "#32D882",
          primaryDark: "#18965A",
          accent: "#FF6B00",
          dark: "#103A26",
        },
        tr: {
          navy: "#103A26",
          navy2: "#1A5A3A",
          teal: "#1F8F58",
          cyan2: "#32D882",
          pale: "#EAF8F0",
          body: "#2F4A3B",
          mute: "#6B7F73",
          line: "#D7EBDD",
          landingOrange: "#F8A51B",
          navyDeep: "#0A2418",
          ice: "#F4FCF7",
          page: "#F8FAFC",
        },
        status: {
          cited: "#22C55E",
          citedSoft: "#86EFAC",
          comp: "#F59E0B",
          none: "#EF4444",
          running: "#32D882",
          queued: "#E2E8F0",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-dm)", "DM Sans", "var(--font-inter)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 4px 24px rgba(16, 58, 38, 0.08)",
        lift: "0 12px 40px rgba(16, 58, 38, 0.12)",
      },
    },
  },
  plugins: [],
};
export default config;
