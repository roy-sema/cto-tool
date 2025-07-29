import "@/common/apexcharts/styles.css";
import "@/compass/assets/styles/base.scss";

import * as Sentry from "@sentry/vue";

import { DjangoUtilsPlugin, convertDatasetToProps } from "vue-plugin-django-utils";
import posthogPlugin from "./plugins/posthog";
import { router, routes } from "./router";

import { definePreset } from "@primevue/themes";
import Aura from "@primevue/themes/aura";
import { createPinia } from "pinia";
import PrimeVue from "primevue/config";
import ConfirmationService from "primevue/confirmationservice";
import ToastService from "primevue/toastservice";
import { createApp } from "vue";
import App from "./compass/App.vue";

const currentPath = window.location.pathname;

const appEl = document.getElementById("vue-app") || document.getElementById("vue-app-compat");

const isLegacyApp = currentPath.startsWith("/genai-radar/") || currentPath.startsWith("/settings/");

// Hack for legacy views
let component;
if (isLegacyApp) {
  const pages = Object.fromEntries(routes.map((route) => [route.path.replace(":path?", ""), route.component]));
  component = Object.entries(pages).find(([path]) => currentPath.includes(path))?.[1];
} else {
  component = App;
}

// Source: https://stackoverflow.com/questions/3561493/is-there-a-regexp-escape-function-in-javascript
const escapeRegex = (string: string): string => string.replace(/[/\-\\^$*+?.()|[\]{}]/g, "\\$&");

// TODO: use Sema colors
const primaryColor = "sky";
const variants = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
const SemaPreset = definePreset(Aura, {
  semantic: {
    primary: variants.reduce(
      (obj, variant) => {
        obj[variant] = "{" + primaryColor + "." + variant + "}";
        return obj;
      },
      {} as Record<number, string>,
    ),
    colorScheme: {
      dark: {
        surface: {
          0: "#ffffff",
          50: "{slate.50}",
          100: "{slate.100}",
          200: "{slate.200}",
          300: "{slate.300}",
          400: "{slate.400}",
          500: "{slate.500}",
          600: "{slate.600}",
          700: "{slate.700}",
          800: "{slate.800}",
          900: "{slate.900}",
          950: "{slate.950}",
        },
      },
    },
  },
});

if (appEl && component) {
  const props = convertDatasetToProps({ dataset: { ...appEl.dataset }, component });

  const app = createApp(component, props);

  const dsn = import.meta.env.VITE_SENTRY_DSN;
  const domain = import.meta.env.VITE_SITE_DOMAIN;
  if (dsn && domain) {
    Sentry.init({
      app,
      dsn,
      integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
      // Performance Monitoring
      tracesSampleRate: 1.0,
      tracePropagationTargets: ["^" + escapeRegex(domain)],
      replaysSessionSampleRate: 0.1,
      replaysOnErrorSampleRate: 1.0,
    });

    const email = app._props?.userEmail;
    if (typeof email === "string") {
      Sentry.setUser({ email: email });
    }

    const organization = app._props?.organizationName;
    if (typeof organization === "string") {
      Sentry.setExtra("organization", organization);
    }
  }

  app.use(PrimeVue, {
    theme: {
      preset: SemaPreset,
      options: {
        darkModeSelector: ".dark",
      },
    },
  });
  app.use(ConfirmationService);
  app.use(ToastService);

  app.use(DjangoUtilsPlugin, { rootElement: appEl });

  const pinia = createPinia();
  pinia.use(Sentry.createSentryPiniaPlugin());
  app.use(pinia);

  app.use(posthogPlugin);
  app.use(router);
  app.mount(appEl);
}
