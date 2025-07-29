<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import StackedBarChart from "@/common/components/StackedBarChart.vue";
import ConnectedModules from "@/compass/components/codebasereports/ConnectedModules.vue";
import InsightText from "@/compass/components/codebasereports/InsightText.vue";
import InsightTextWarningsBenchmark from "@/compass/components/codebasereports/InsightTextWarningsBenchmark.vue";
import NavigateButtons from "@/compass/components/codebasereports/NavigateButtons.vue";
import ScoreCard from "@/compass/components/codebasereports/ScoreCard.vue";
import ScoreText from "@/compass/components/codebasereports/ScoreText.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import { getCodebaseExecutiveSummary } from "@/compass/helpers/api";
import type { Insight, Score } from "@/compass/helpers/api.d";
import { ExclamationTriangleIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { subDays } from "date-fns";
import { onMounted, ref } from "vue";

const date = ref<[Date, Date] | null>(null);
const loading = ref(true);
const loadingCharts = ref(false);

const caveats = ref({});
const chartSemaComplianceScore = ref({ no_data: true });
const chartSemaProductScore = ref({ no_data: true });
const chartSemaScore = ref({ no_data: true });
const connections = ref<Record<string, string | null>>({});
const defaultTimeWindowDays = ref();
const insightCommits = ref<Insight>();
const insightFiles = ref<Insight>();
const insightHighCve = ref<Insight>();
const insightHighSast = ref<Insight>();
const modules = ref<Record<string, any>>();
const orgFirstDate = ref();
const semaComplianceScore = ref<Score>({ score: 0 });
const semaProductScore = ref<Score>({ score: 0 });
const semaScore = ref<Score>({ score: 0 });
const semaScoreDiff = ref(0);
const semaScoreLastWeek = ref<Score>({ score: 0 });
const updatedAt = ref(0);
const dateRange = ref<[Date, Date]>();
const integrations = ref<IntegrationStatusMap>();

const loadData = async () => {
  try {
    loading.value = true;

    const response = await getCodebaseExecutiveSummary();
    setChartsData(response);
    caveats.value = response.caveats;
    connections.value = response.connections;
    integrations.value = response.integrations;
    defaultTimeWindowDays.value = response.default_time_window_days;
    insightCommits.value = response.insight_commits;
    insightFiles.value = response.insight_files;
    insightHighCve.value = response.insight_high_cve;
    insightHighSast.value = response.insight_high_sast;
    modules.value = response.modules;
    orgFirstDate.value = response.org_first_date;
    semaComplianceScore.value = response.sema_compliance_score || { score: 0 };
    semaProductScore.value = response.sema_product_score || { score: 0 };
    semaScore.value = response.sema_score || { score: 0 };
    semaScoreDiff.value = response.sema_score_diff || 0;
    semaScoreLastWeek.value = response.sema_score_last_week || { score: 0 };
    updatedAt.value = response.updated_at || 0;
    dateRange.value = [new Date(response.since), new Date(response.until)];

    // Set initial dates
    if (!date.value) {
      const until = new Date();
      const since = subDays(until, defaultTimeWindowDays.value);
      date.value = [since, until];
    }
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const setChartsData = (response: any) => {
  chartSemaComplianceScore.value = response.chart_sema_compliance_score || { no_data: true };
  chartSemaProductScore.value = response.chart_sema_product_score || { no_data: true };
  chartSemaScore.value = response.chart_sema_score || { no_data: true };
};

const updateCharts = async (since?: string, until?: string) => {
  try {
    loadingCharts.value = true;

    const response = await getCodebaseExecutiveSummary(since, until);
    setChartsData(response);
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loadingCharts.value = false;
  }
};

const smartDateHandler = (value: string[]) => {
  if (value && value.length === 2) {
    updateCharts(value[0], value[1]);
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader
    title="Executive Summary"
    :updatedAt="updatedAt"
    :integrations="integrations"
    :loading="loading"
    :dateRange="dateRange"
  />

  <div class="flex flex-col justify-between gap-5 px-4 py-5 lg:px-6">
    <template v-for="(lastFetchedAt, provider) in connections">
      <Message v-if="!lastFetchedAt" severity="warn">
        <p class="text-sm">We are still fetching data for {{ provider }}. Please come back later.</p>
      </Message>
    </template>

    <div v-if="loading" class="flex items-center justify-center">
      <ProgressSpinner />
    </div>
    <Message v-else-if="!Object.keys(connections).length" severity="warn">
      Please connect your tools to start gathering data.
    </Message>
    <div v-else class="w-full">
      <div v-if="caveats" class="flex flex-col gap-5">
        <Message v-for="(caveatText, caveatId) in caveats" :key="caveatId" severity="info">
          <p class="text-sm">
            <ExclamationTriangleIcon class="inline size-4" />
            {{ caveatText }}
            <a
              v-if="caveatId === 'sema_score'"
              href="https://announcekit.co/semasoftware/release-notes/"
              title="Release notes"
              target="_blank"
              rel="noopener noreferrer"
              class="font-semibold text-blue hover:text-violet dark:hover:text-lightgrey"
              >Read more here</a
            >
          </p>
          <p class="mt-1 text-sm font-semibold">Therefore a historical comparison may not be apples-to-apples.</p>
        </Message>
      </div>

      <div class="mb-10 mt-5 grid gap-5 md:grid-cols-2">
        <ScoreCard
          title="Codebase Health Score"
          :score="semaScore"
          :max="100"
          tooltipSuffix=""
          :difference="semaScoreDiff"
          :noChart="true"
        />
        <div class="mb-10 flex w-full items-center justify-center md:h-40 md:h-60">
          <div class="text-center md:text-left">
            <ScoreText :score="semaScore" :scoreLastWeek="semaScoreLastWeek" />
          </div>
        </div>
      </div>

      <ConnectedModules v-if="modules" :modules="modules" />

      <Divider />

      <div class="flex justify-end">
        <RangeDatePicker
          class="!w-full md:!w-56"
          :date="date"
          :firstDate="orgFirstDate"
          @update:date="smartDateHandler"
        />
      </div>

      <div class="mt-10 grid gap-x-5 gap-y-10 md:mt-0 md:grid-cols-3">
        <div class="md:col-span-3">
          <StackedBarChart
            id="sema-score"
            title="Codebase Health Score"
            :data="chartSemaScore"
            :maxY="100"
            tooltipSuffix=""
            :loading="loadingCharts"
          />
        </div>

        <ScoreCard :title="'Product Score'" :score="semaProductScore" :max="100" tooltipSuffix="" />
        <div class="md:col-span-2">
          <StackedBarChart
            id="sema-product-score"
            title="Product Score"
            :data="chartSemaProductScore"
            :maxY="100"
            tooltipSuffix=""
            :loading="loadingCharts"
          />
        </div>

        <ScoreCard :title="'Compliance Score'" :score="semaComplianceScore" :max="100" tooltipSuffix="" />
        <div class="md:col-span-2">
          <StackedBarChart
            id="sema-compliance-score"
            title="Compliance Score"
            :data="chartSemaComplianceScore"
            :maxY="100"
            tooltipSuffix=""
            :loading="loadingCharts"
          />
        </div>
      </div>

      <div v-if="insightCommits || insightFiles">
        <h3 class="mb-4 mt-10 text-lg font-semibold">Product Insights</h3>

        <h4 class="my-4 font-semibold">Process</h4>

        <InsightText
          v-if="insightCommits"
          :text="insightCommits.text"
          :level="insightCommits.level"
          :status="insightCommits.status"
          :description="insightCommits.description"
        />
        <InsightText
          v-if="insightFiles"
          :text="insightFiles.text"
          :level="insightFiles.level"
          :status="insightFiles.status"
          :description="insightFiles.description"
        />
      </div>

      <div v-if="insightHighSast || insightHighCve">
        <h3 class="mb-4 mt-10 text-lg font-semibold">Compliance Insights</h3>

        <h4 class="my-4 font-semibold">Code Security</h4>

        <InsightTextWarningsBenchmark
          v-if="insightHighSast"
          :insight="insightHighSast"
          warningType="in-file security"
        />
        <InsightTextWarningsBenchmark v-if="insightHighCve" :insight="insightHighCve" warningType="CVEs" />
      </div>

      <NavigateButtons exclude="executive-summary" />
    </div>
  </div>
</template>
