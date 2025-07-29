import type { Config } from "tailwindcss";
import tailwindcssPrimeui from "tailwindcss-primeui";
import twElements from "tw-elements/plugin.cjs";

const config: Config = {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}", "./node_modules/tw-elements/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        blue: "#0081A7",
        pink: "#E80673",
        violet: "#2A113F",
        lightgrey: "#F7F7F7",
        dark: "#202020",
        // TODO: add level colors
      },
      fontFamily: {
        sans: "Inter, sans-serif",
      },
    },
  },
  darkMode: "class",
  plugins: [tailwindcssPrimeui, twElements],
};

export default config;
