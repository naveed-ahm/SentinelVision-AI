/** @type {import('tailwindcss').Config} */
// LIGHT THEME — surface tokens keep their semantic names so components stay
// unchanged: navy.* is now the light surface scale (page → chrome → card → hover).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surface scale (was dark navy, now light):
        navy: {
          DEFAULT: "#F1F5F9", // page background (slate-100)
          800: "#FFFFFF", // sidebar / topbar chrome
          700: "#FFFFFF", // card background
          600: "#F1F5F9", // hover surface
        },
        accent: {
          DEFAULT: "#2563EB",
          bright: "#1D4ED8",
        },
        ok: "#16A34A",
        warn: "#D97706",
        crit: "#DC2626",
        body: "#0F172A", // primary text (slate-900)
        muted: "#64748B", // secondary text (slate-500)
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
