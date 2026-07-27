import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0F1118",
        panel: "#1E2130",
        accent: "#2962FF",
      },
    },
  },
  plugins: [],
};

export default config;
