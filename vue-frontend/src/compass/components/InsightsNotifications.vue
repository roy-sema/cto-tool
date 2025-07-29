<script setup lang="ts">
import DailyMessageFilterForm from "@/compass/components/DailyMessageFilterForm.vue";
import { completeOnboarding, getInsightsNotifications, setInsightsNotifications } from "@/compass/helpers/api";
import { useUserStore } from "@/compass/stores/user";
import { CheckIcon, DocumentIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

withDefaults(
  defineProps<{
    showContinueButton?: boolean;
    showFilters?: boolean;
  }>(),
  {
    showContinueButton: true,
    showFilters: true,
  },
);

const router = useRouter();
const userStore = useUserStore();

const loadingAnomaly = ref<boolean>(false);
const loadingComplete = ref<boolean>(false);
const loadingSummary = ref<boolean>(false);
const anomalyInsights = ref<boolean>(false);
const summaryInsights = ref<boolean>(false);

async function onSaveInsightsNotifications(anomaly: boolean, summary: boolean) {
  if (anomaly != anomalyInsights.value) loadingAnomaly.value = true;
  if (summary != summaryInsights.value) loadingSummary.value = true;
  try {
    const response = await setInsightsNotifications(anomaly, summary);
    anomalyInsights.value = response.anomaly_insights;
    summaryInsights.value = response.summary_insights;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loadingAnomaly.value = false;
    loadingSummary.value = false;
  }
}

const buttonLabel = (loading: boolean, insights: boolean) => {
  if (loading) return "";
  return insights ? "Subscribed" : "Subscribe";
};

const anomalyButtonLabel = computed(() => buttonLabel(loadingAnomaly.value, anomalyInsights.value));

const loadData = async () => {
  loadingAnomaly.value = true;
  loadingSummary.value = true;
  try {
    const response = await getInsightsNotifications();
    anomalyInsights.value = response.anomaly_insights;
    summaryInsights.value = response.summary_insights;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loadingAnomaly.value = false;
    loadingSummary.value = false;
  }
};

const complete = async () => {
  loadingComplete.value = true;

  try {
    await completeOnboarding();
    userStore.setOnboardingCompleted(true);
    router.push({ name: "home" });
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loadingComplete.value = false;
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="my-5 flex flex-col">
    <div class="mx-auto w-3/4 max-w-3xl">
      <Card>
        <template #content>
          <div>
            <h2 class="mb-5 text-lg font-semibold">Sign up for prioritized insights about your products</h2>
            <div class="justify-between rounded border border-gray-500 p-5 xl:flex">
              <div>
                <div class="flex">
                  <div class="flex items-center">
                    <DocumentIcon class="size-10 md:size-5" />
                  </div>
                  <div class="ml-2 gap-2 md:flex">
                    <p>Anomaly Insights:</p>
                    <p class="text-blue">Once a day</p>
                  </div>
                </div>
                <p class="text-gray-500">Significant changes</p>
              </div>
              <div class="items-ce mt-2 flex items-center xl:mt-0">
                <Button
                  class="mx-auto max-h-10 !w-36"
                  :label="anomalyButtonLabel"
                  :severity="anomalyInsights ? 'success' : 'info'"
                  :outlined="anomalyInsights"
                  :loading="loadingAnomaly"
                  @click="onSaveInsightsNotifications(!anomalyInsights, summaryInsights)"
                >
                  <template #icon>
                    <CheckIcon v-if="anomalyInsights" class="mr-1 size-5" />
                  </template>
                </Button>
              </div>
            </div>
          </div>
        </template>
      </Card>
      <DailyMessageFilterForm v-if="showFilters" />
      <div v-if="showContinueButton" class="ml-auto mt-4 flex items-center justify-end space-x-4 pb-10 xl:pb-0">
        <Button
          :label="loadingComplete ? 'Finishing Onboarding' : 'Finish Onboarding'"
          :loading="loadingComplete"
          @click="complete"
        />
      </div>
    </div>
  </div>
</template>
