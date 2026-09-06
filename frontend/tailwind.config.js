/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ocean: {
          midnight: "#071E2E",
          deep: "#0B2A3D",
          blue: "#0E7490",
          teal: "#0891B2",
          aqua: "#22D3EE",
          success: "#10B981",
          ice: "#F4FAFC",
          surface: "#FFFFFF",
          slate: "#1E293B",
          muted: "#64748B",
          warning: "#F59E0B",
          critical: "#EF5B5B",
          border: "#CBDDE5",
        },
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      borderRadius: {
        card: "12px",
      },
      boxShadow: {
        card: "0 1px 3px rgba(7, 30, 46, 0.08), 0 1px 2px rgba(7, 30, 46, 0.06)",
        panel: "0 4px 6px rgba(7, 30, 46, 0.07)",
      },
    },
  },
  plugins: [],
};
