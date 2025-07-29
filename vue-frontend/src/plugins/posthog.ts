import posthog from "posthog-js";
import type { App } from "vue";

const posthogAPIKey = import.meta.env.VITE_POSTHOG_PROJECT_API_KEY;
const posthogAddress = import.meta.env.VITE_POSTHOG_INSTANCE_ADDRESS;

export default {
  install(app: App) {
    if (posthogAPIKey && posthogAddress) {
      app.config.globalProperties.$posthog = posthog.init(posthogAPIKey, {
        api_host: posthogAddress,
        // Needed for tracking page views https://posthog.com/tutorials/single-page-app-pageviews
        defaults: "2025-05-24",
      });
    } else {
      console.warn(
        "PostHog is not configured. Please set the POSTHOG_API_KEY and POSTHOG_INSTANCE_ADDRESS environment variables, ignore if this is a local dev environment.",
      );
    }
  },
};
