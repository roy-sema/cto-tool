<script setup lang="ts">
import { round } from "@/aicm/helpers/utils";
import type { IntegrationStatusMap } from "@/common/api.d";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import ProductRoadmapRadarPanel from "@/compass/components/sip/ProductRoadmapRadarPanel.vue";
import { getSIPProductRoadmapRadarData } from "@/compass/helpers/api";
import * as Sentry from "@sentry/vue";
import { onMounted, ref } from "vue";

const loading = ref(false);
const updated_at = ref();
const integrations = ref<IntegrationStatusMap>();
const initiatives = ref();
const developmentActivity = ref();
const dailyMessage = ref();
const rawResults = ref();
const ticketCompleteness = ref();
const anomalyInsights = ref();

const loadData = async () => {
  try {
    loading.value = true;
    const response = await getSIPProductRoadmapRadarData();

    updated_at.value = response.updated_at;
    integrations.value = response.integrations;

    initiatives.value = response.initiatives;
    developmentActivity.value = response.development_activity;
    dailyMessage.value = response.daily_message;
    rawResults.value = response.raw_results;
    ticketCompleteness.value = response.ticket_completeness;
    anomalyInsights.value = response.anomaly_insights;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="mx-auto min-h-screen max-w-7xl px-4 pb-4 sm:px-6 xl:px-2">
    <PageHeader
      class="!px-0"
      title="Product Roadmap Radar"
      :updatedAt="updated_at"
      :integrations="integrations"
      :loading="loading"
    />

    <div>
      <div class="my-5 grid gap-5 sm:grid-cols-3">
        <ProductRoadmapRadarPanel
          title="Daily Message"
          :updatedAt="dailyMessage?.updated_at"
          :to="{ name: 'daily-message' }"
          urlLabel="Go to Daily Message"
          :loading="loading"
          :tiny="true"
        />

        <ProductRoadmapRadarPanel
          title="Product Roadmap Overview"
          :updatedAt="initiatives?.updated_at"
          :to="{ name: 'roadmap' }"
          urlLabel="Go to the Product Roadmap"
          :loading="loading"
          :tiny="true"
        >
          <div class="mb-2">
            <span class="text-xl font-bold text-blue">{{ initiatives?.count }}</span>
            <span class="text-gray-600"> total {{ initiatives?.count === 1 ? "Initiative" : "Initiatives" }}</span>
          </div>
        </ProductRoadmapRadarPanel>

        <ProductRoadmapRadarPanel
          title="Development Activity"
          :updatedAt="developmentActivity?.updated_at"
          :to="{ name: 'development-activity' }"
          urlLabel="Go to the Development Activity"
          :loading="loading"
          :tiny="true"
        >
          <div class="space-y-1">
            <div v-if="developmentActivity?.activities?.length">
              <div
                v-for="(activity, index) in developmentActivity?.activities"
                :key="index"
                class="flex items-center justify-between gap-2"
              >
                <span>{{ activity.name }}</span>
                <span class="text-blue">{{ round(activity.percentage) }}%</span>
              </div>
            </div>
            <div v-else class="space-y-1 text-muted-color">There's no data to report.</div>
          </div>
        </ProductRoadmapRadarPanel>
      </div>

      <div class="my-5 grid gap-5 sm:grid-cols-2">
        <ProductRoadmapRadarPanel
          title="Ticket Completeness Score"
          :updatedAt="ticketCompleteness?.updated_at"
          :to="{ name: 'ticket-completeness' }"
          urlLabel="Go to Ticket Completeness Dashboard"
          :loading="loading"
          :tiny="true"
        >
          <div class="mb-2">
            <span class="text-3xl font-bold text-blue">{{ ticketCompleteness?.average_score || "--" }}</span>
            <span class="text-gray-600"> organization average</span>
          </div>
        </ProductRoadmapRadarPanel>

        <ProductRoadmapRadarPanel
          title="Anomaly Insights"
          :updatedAt="anomalyInsights?.updated_at"
          :to="{ name: 'anomaly-insights' }"
          urlLabel="Go to Anomaly Insights Dashboard"
          :loading="loading"
          :tiny="true"
        />
      </div>

      <div class="my-5 grid gap-5 sm:grid-cols-2">
        <ProductRoadmapRadarPanel
          title="Raw Results"
          :updatedAt="rawResults?.updated_at"
          :to="{ name: 'raw-contextualization-data' }"
          urlLabel="Go to Raw Results"
          :loading="loading"
          :beta="true"
          :tiny="true"
        />

        <ProductRoadmapRadarPanel
          title="File Upload"
          :to="{ name: 'file-uploads' }"
          urlLabel="Go to File Upload"
          :loading="loading"
          :tiny="true"
        />
      </div>
    </div>
  </div>
</template>
