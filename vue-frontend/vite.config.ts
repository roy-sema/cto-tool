import { resolve as path_resolve } from "node:path";
import { URL, fileURLToPath } from "node:url";

import { PrimeVueResolver } from "@primevue/auto-import-resolver";
import { sentryVitePlugin } from "@sentry/vite-plugin";
import vue from "@vitejs/plugin-vue";
import Components from "unplugin-vue-components/vite";
import { defineConfig } from "vite";
import cssInjectedByJsPlugin from "vite-plugin-css-injected-by-js";
import svgLoader from "vite-svg-loader";

// https://vitejs.dev/config/
export default defineConfig({
  envDir: "../",
  plugins: [
    vue(),
    Components({
      resolvers: [PrimeVueResolver()],
    }),
    cssInjectedByJsPlugin({ jsAssetsFilterFunction: () => true }),
    sentryVitePlugin({
      org: "sema-i6",
      project: "django-vue",
    }),
    svgLoader(),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      input: {
        app: path_resolve("./src/app.ts"),
      },
      output: {
        dir: "../mvp/static/vue/",
        entryFileNames: "[name].js",
      },
    },

    sourcemap: true,
  },
});
