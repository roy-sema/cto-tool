<script setup lang="ts">
import AttestationPercentagesTable from "@/aicm/components/AttestationPercentagesTable.vue";
import AISummary from "@/aicm/components/common/AISummary.vue";
import LineMiniChart from "@/aicm/components/common/LineMiniChart.vue";
import SwitchInput from "@/aicm/components/common/SwitchInput.vue";
import Teleports from "@/aicm/components/common/Teleports.vue";
import ROIPanel from "@/aicm/components/RepositoryGroup/ROIPanel.vue";
import { getRepositoriesComposition } from "@/aicm/helpers/api";
import type { ROIFields } from "@/aicm/helpers/api.d";
import type { IntegrationStatusMap } from "@/common/api.d";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import { QuestionMarkCircleIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import type { Ref } from "vue";
import { computed, ref } from "vue";

const props = defineProps({
  aiComposition: { type: String, default: "{}" },
  cumulativeCharts: { type: String, default: "[]" },
  dailyCharts: { type: String, default: "[]" },
  evaluatedPercentage: { type: String, default: "0" },
  orgFirstDate: { type: String, default: "" },
  roiData: { type: String, default: "{}" },
  codeAttestationPercentages: { type: String, default: "{}" },
  integrations: { type: String, default: "[]" },
  updatedAt: { type: Number, default: 0 },
});

const aiComposition = ref(JSON.parse(props.aiComposition));
const cumulativeCharts = ref(JSON.parse(props.cumulativeCharts));
const dailyCharts = ref(JSON.parse(props.dailyCharts));
const evaluatedPercentage = ref(JSON.parse(props.evaluatedPercentage));
const filteredCumulativeCharts = ref([...cumulativeCharts.value]);
const filteredDailyCharts = ref([...dailyCharts.value]);
const roiData = ref<ROIFields>(JSON.parse(props.roiData));
const codeAttestationPercentages = ref<ROIFields>(JSON.parse(props.codeAttestationPercentages));
const integrations = ref<IntegrationStatusMap>(JSON.parse(props.integrations));
const updatedAt = ref(props.updatedAt);

const date = ref<[Date, Date] | null>(null);
const dateRange = ref<[Date, Date] | null>(null);
const dynamicChartYAxis = ref(true);
const chartMaxY = computed(() => (dynamicChartYAxis.value ? null : 100));

// Set initial dates
if (cumulativeCharts.value.length) {
  const categories = cumulativeCharts.value[0]?.data?.categories;
  const start_date = new Date(categories[0]);
  const end_date = new Date(categories[categories.length - 1]);
  date.value = [start_date, end_date];
  dateRange.value = [start_date, end_date];
}

let loading: Ref<boolean> = ref(false);
const errorText = ref("");

const fetchFilteredCharts = async (since: string, until: string) => {
  try {
    errorText.value = "";
    loading.value = true;
    const response = await getRepositoriesComposition(since, until);
    filteredCumulativeCharts.value = response.cumulative_charts;
    filteredDailyCharts.value = response.daily_charts;
    aiComposition.value = response.ai_composition;
    dateRange.value = [new Date(since), new Date(until)];
  } catch (error) {
    Sentry.captureException(error);
    errorText.value = "An Error has occurred. Please refresh the page or try again later.";
  } finally {
    loading.value = false;
  }
};

const smartDateHandler = (value: string[]) => {
  if (value && value.length === 2) {
    fetchFilteredCharts(value[0], value[1]);
  }
};

const showROIPanel = computed(
  () => roiData.value.potential_productivity_captured != null && roiData.value.productivity_achievement != null,
);
</script>

<template>
  <PageHeader
    title="GenAI Codebase Composition"
    :dateRange="dateRange"
    :updatedAt="updatedAt"
    :integrations="integrations"
    :loading="loading"
    class="-mx-4 -mt-4 lg:-mx-6"
  />

  <div>
    <div class="my-4">
      <ROIPanel
        v-if="showROIPanel"
        :productivityAchievement="roiData.productivity_achievement"
        :potentialProductivityCaptured="roiData.potential_productivity_captured"
        :costSaved="roiData.cost_saved"
        :hoursSaved="roiData.hours_saved"
        :toolsCostSavedPercentage="roiData.tools_cost_saved_percentage"
        :debugData="roiData.debug_data"
      />
    </div>
    <div class="mt-5 flex flex-col">
      <div class="mb-4 flex justify-end">
        <RangeDatePicker :date="date" :firstDate="orgFirstDate" @update:date="smartDateHandler" />
      </div>

      <div
        v-if="errorText"
        class="relative mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-sm text-red-700"
        role="alert"
      >
        {{ errorText }}
      </div>

      <AISummary
        :aiComposition="aiComposition"
        :evaluatedPercentage="evaluatedPercentage"
        :loading="loading"
        :trend="true"
      />

      <div v-if="filteredCumulativeCharts.length" class="mt-5 items-center justify-between sm:flex">
        <h2 class="mt-10 text-xl font-semibold md:text-2xl">
          Cumulative usage <sup>BETA</sup>
          <div
            class="ml-1 inline-block"
            data-te-toggle="popover"
            data-te-content="Composition of all the code in all repositories, up to that day"
            data-te-trigger="hover focus"
          >
            <QuestionMarkCircleIcon class="inline w-5 cursor-help opacity-80" />
          </div>
        </h2>

        <div class="relative mt-2 self-end">
          <SwitchInput id="blameSwitch" v-model="dynamicChartYAxis" />
          <label class="inline-block ps-[0.15rem] text-sm hover:cursor-pointer" for="blameSwitch">
            Dynamic scale
          </label>
          <div
            class="ml-1 inline-block"
            data-te-toggle="popover"
            data-te-content="When active (default), the Y-axis will adjust to the highest value in the chart. When disabled, the Y-axis will be fixed at 0-100%."
            data-te-trigger="hover focus"
          >
            <QuestionMarkCircleIcon class="inline w-4 cursor-help opacity-80" />
          </div>
        </div>
      </div>

      <div class="mt-5 grid gap-5" :class="`md:grid-cols-${aiComposition.length}`">
        <LineMiniChart
          v-for="chart in filteredCumulativeCharts"
          :id="chart.id"
          :key="chart.id"
          :title="chart.label + ' (%)'"
          :data="chart.data"
          :loading="loading"
          :maxY="chartMaxY"
        />
      </div>

      <h2 v-if="filteredDailyCharts.length" class="mt-10 text-xl font-semibold md:text-2xl">
        Usage in time period <sup>BETA</sup>
        <div
          class="ml-1 inline-block"
          data-te-toggle="popover"
          data-te-content="Composition of all pushed code on that day"
          data-te-trigger="hover focus"
        >
          <QuestionMarkCircleIcon class="inline w-5 cursor-help opacity-80" />
        </div>
      </h2>

      <div class="mt-5 grid gap-5" :class="`md:grid-cols-${aiComposition.length}`">
        <LineMiniChart
          v-for="chart in filteredDailyCharts"
          :id="chart.id"
          :key="chart.id"
          :title="chart.label + ' (%)'"
          :data="chart.data"
          :loading="loading"
          :maxY="chartMaxY"
        />
      </div>
    </div>
    <AttestationPercentagesTable v-if="codeAttestationPercentages" :codeAttestationPercentages />

    <Teleports />
  </div>
</template>
