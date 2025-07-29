<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import StackedBarChart from "@/common/components/StackedBarChart.vue";
import ExportChartCsv from "@/compass/components/codebasereports/ExportChartCsv.vue";
import InsightText from "@/compass/components/codebasereports/InsightText.vue";
import NavigateButtons from "@/compass/components/codebasereports/NavigateButtons.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import { getCodebaseProductDetail } from "@/compass/helpers/api";
import type { Insight } from "@/compass/helpers/api.d";
import * as Sentry from "@sentry/vue";
import { subDays } from "date-fns";
import { computed, onMounted, ref } from "vue";

const date = ref<[Date, Date] | null>(null);
const loading = ref(true);
const loadingCharts = ref(false);

const chartCodacyComplexity = ref({ no_data: true });
const chartCodacyCoverage = ref({ no_data: true });
const chartCodacyCoveragePercentage = ref({ no_data: true });
const chartCodacyDuplication = ref({ no_data: true });
const chartCodacyIssues = ref({ no_data: true });
const chartProcessCommits = ref({ no_data: true });
const chartProcessFiles = ref({ no_data: true });
const chartTeamDevelopers = ref({ no_data: true });
const chartTeamDevelopersPercentage = ref({ no_data: true });
const connections = ref<Record<string, string | null>>({});
const integrations = ref<IntegrationStatusMap>();
const defaultTimeWindowDays = ref();
const insightCommits = ref<Insight>();
const insightFiles = ref<Insight>();
const modules = ref<Record<string, any>>();
const orgFirstDate = ref();
const updatedAt = ref(0);
const dateRange = ref<[Date, Date]>();

const hasCodacyData = computed(() => {
  return (
    chartCodacyIssues.value || chartCodacyComplexity.value || chartCodacyDuplication.value || chartCodacyCoverage.value
  );
});

const hasProcessData = computed(() => {
  return chartProcessCommits.value || chartProcessFiles.value;
});

const hasTeamData = computed(() => {
  return chartTeamDevelopers.value || chartTeamDevelopersPercentage.value;
});

const loadData = async () => {
  try {
    loading.value = true;

    const response = await getCodebaseProductDetail();
    setChartsData(response);
    connections.value = response.connections;
    defaultTimeWindowDays.value = response.default_time_window_days;
    insightCommits.value = response.insight_commits;
    insightFiles.value = response.insight_files;
    modules.value = response.modules;
    orgFirstDate.value = response.org_first_date;
    updatedAt.value = response.updated_at || 0;
    updatedAt.value = response.updated_at;
    dateRange.value = [new Date(response.since), new Date(response.until)];
    integrations.value = response.integrations;

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
  chartCodacyComplexity.value = response.chart_codacy_complexity || { no_data: true };
  chartCodacyCoverage.value = response.chart_codacy_coverage || { no_data: true };
  chartCodacyCoveragePercentage.value = response.chart_codacy_coverage_percentage || { no_data: true };
  chartCodacyDuplication.value = response.chart_codacy_duplication || { no_data: true };
  chartCodacyIssues.value = response.chart_codacy_issues || { no_data: true };
  chartProcessCommits.value = response.chart_process_commits || { no_data: true };
  chartProcessFiles.value = response.chart_process_files || { no_data: true };
  chartTeamDevelopers.value = response.chart_team_developers || { no_data: true };
  chartTeamDevelopersPercentage.value = response.chart_team_developers_percentage || { no_data: true };
};

const updateCharts = async (since?: string, until?: string) => {
  try {
    loadingCharts.value = true;

    const response = await getCodebaseProductDetail(since, until);
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
    title="Product Detail"
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
      <div class="flex justify-end md:-mb-5">
        <RangeDatePicker
          class="!w-full md:!w-56"
          :date="date"
          :firstDate="orgFirstDate"
          @update:date="smartDateHandler"
        />
      </div>

      <h3 class="mb-4 mt-10 text-xl font-semibold md:mt-0">Code Quality</h3>
      <div>
        <p v-if="!modules?.Product?.code_quality?.connected" class="mb-10 mt-5">
          Please
          <a href="/settings/connections/" class="font-semibold text-blue">connect your code quality tool</a> to start
          gathering data.
        </p>
        <p v-else-if="!hasCodacyData" class="mb-10 mt-5">
          We are still fetching data from Codacy, please come back later.
        </p>
        <div v-else class="mb-10 mt-5 grid gap-x-5 gap-y-10 md:grid-cols-3">
          <div v-if="chartCodacyIssues" class="md:col-span-2">
            <StackedBarChart
              id="codacy-issues"
              title="Code Quality: Number of issues"
              :data="chartCodacyIssues"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartCodacyComplexity" class="md:col-span-2">
            <StackedBarChart
              id="codacy-complexity"
              title="Code Quality: Complexity of code"
              :data="chartCodacyComplexity"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartCodacyDuplication" class="md:col-span-2">
            <StackedBarChart
              id="codacy-duplication"
              title="Code Quality: Number of duplicated lines"
              :data="chartCodacyDuplication"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartCodacyCoverage" class="md:col-span-2">
            <StackedBarChart
              id="codacy-coverage"
              title="Code Quality: Number of files uncovered by automated tests"
              :data="chartCodacyCoverage"
              :loading="loadingCharts"
              no-data-message="Check Codacy is configured to get Coverage metrics."
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
        </div>
      </div>

      <h3 class="mb-4 mt-10 text-xl font-semibold">Process</h3>
      <div>
        <p v-if="!modules?.Product?.process?.connected" class="mb-10 mt-5">
          Please
          <a href="/settings/connections/" class="font-semibold text-blue">connect your process tool</a> to start
          gathering data.
        </p>
        <p v-else-if="!hasProcessData" class="mb-10 mt-5">We are still fetching data, please come back later.</p>
        <div v-else class="mb-10 mt-5 grid gap-x-5 gap-y-10 md:grid-cols-3">
          <div v-if="chartProcessCommits" class="md:col-span-2">
            <StackedBarChart
              id="process-commits"
              title="Process: Commits over time"
              :data="chartProcessCommits"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartProcessCommits && insightCommits" class="md:mt-9">
            <InsightText
              :text="insightCommits.text"
              :level="insightCommits.level"
              :status="insightCommits.status"
              :description="insightCommits.description"
            />
          </div>
          <div v-if="chartProcessFiles" class="md:col-span-2">
            <StackedBarChart
              id="process-files"
              title="Process: File changes over time"
              :data="chartProcessFiles"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartProcessFiles && insightFiles" class="md:mt-9">
            <InsightText
              :text="insightFiles.text"
              :level="insightFiles.level"
              :status="insightFiles.status"
              :description="insightFiles.description"
            />
          </div>
        </div>
      </div>

      <h3 class="mb-4 mt-10 text-xl font-semibold">Team</h3>
      <div>
        <p v-if="!modules?.Product?.team?.connected" class="mb-10 mt-5">
          Please <a href="/settings/connections/" class="font-semibold text-blue">connect your team tool</a> to start
          gathering data.
        </p>
        <p v-else-if="!hasTeamData" class="mb-10 mt-5">We are still fetching data, please come back later.</p>
        <div v-else class="mb-10 mt-5 grid gap-x-5 gap-y-10 md:grid-cols-3">
          <div v-if="chartTeamDevelopers" class="md:col-span-2">
            <StackedBarChart
              id="github-developers"
              title="Team: Developers who worked on the codebase"
              :data="chartTeamDevelopers"
              :loading="loadingCharts"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartTeamDevelopers" class="md:mt-9">
            <ExportChartCsv title="Team: Developers who worked on the codebase" :data="chartTeamDevelopers" />
          </div>
          <div v-if="chartTeamDevelopersPercentage" class="md:col-span-2">
            <StackedBarChart
              id="github-developers-percentage"
              title="Team: % of developers who've worked on the product"
              :data="chartTeamDevelopersPercentage"
              :loading="loadingCharts"
              :maxY="100"
            />
          </div>
          <div v-if="chartTeamDevelopersPercentage" class="md:mt-9">
            <ExportChartCsv
              title="Team: % of developers who've worked on the product"
              :data="chartTeamDevelopersPercentage"
            />
          </div>
        </div>
      </div>

      <NavigateButtons exclude="product-detail" />
    </div>
  </div>
</template>
