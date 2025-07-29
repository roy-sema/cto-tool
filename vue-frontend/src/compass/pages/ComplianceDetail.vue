<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import StackedBarChart from "@/common/components/StackedBarChart.vue";
import CyberSecuritySubmodulesText from "@/compass/components/codebasereports/CyberSecuritySubmodulesText.vue";
import InsightTextWarningsBenchmark from "@/compass/components/codebasereports/InsightTextWarningsBenchmark.vue";
import NavigateButtons from "@/compass/components/codebasereports/NavigateButtons.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import { getCodebaseComplianceDetail } from "@/compass/helpers/api";
import type { Insight } from "@/compass/helpers/api.d";
import * as Sentry from "@sentry/vue";
import { subDays } from "date-fns";
import { computed, onMounted, ref } from "vue";

// the order is "low", "medium", "medium_high", "high":
const SEVERITY_THREE_COLORS = ["#999999", "#FFDE17", "#C10000"];
const SEVERITY_FOUR_COLORS = ["#999999", "#FFDE17", "#FFB03A", "#C10000"];

const date = ref<[Date, Date] | null>(null);
const loading = ref(true);
const loadingCharts = ref(false);

const chartIRadarSubmodulesWithRisk = ref({ no_data: true });
const chartIRadarIssuesCve = ref({ no_data: true });
const chartSnykIssuesCve = ref({ no_data: true });
const chartSnykIssuesLicense = ref({ no_data: true });
const chartSnykIssuesSast = ref({ no_data: true });
const connections = ref<Record<string, string | null>>({});
const integrations = ref<IntegrationStatusMap>();
const defaultTimeWindowDays = ref();
const insightHighCve = ref<Insight>();
const insightHighSast = ref<Insight>();
const iradarSubmodulesDifference = ref();
const modules = ref<Record<string, any>>();
const orgFirstDate = ref();
const updatedAt = ref(0);
const dateRange = ref<[Date, Date] | null>(null);

const hasCyberSecurityData = computed(() => {
  return chartIRadarSubmodulesWithRisk.value || chartIRadarIssuesCve.value;
});

const hasSnykData = computed(() => {
  return chartSnykIssuesSast.value || chartSnykIssuesCve.value;
});

const loadData = async () => {
  try {
    loading.value = true;

    const response = await getCodebaseComplianceDetail();
    setChartsData(response);
    connections.value = response.connections;
    defaultTimeWindowDays.value = response.default_time_window_days;
    insightHighCve.value = response.insight_commits;
    insightHighSast.value = response.insight_files;
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
  chartIRadarSubmodulesWithRisk.value = response.chart_iradar_submodules_with_risk || { no_data: true };
  chartIRadarIssuesCve.value = response.chart_iradar_issues_cve || { no_data: true };
  chartSnykIssuesCve.value = response.chart_snyk_issues_cve || { no_data: true };
  chartSnykIssuesLicense.value = response.chart_snyk_issues_license || { no_data: true };
  chartSnykIssuesSast.value = response.chart_snyk_issues_sast || { no_data: true };
};

const updateCharts = async (since?: string, until?: string) => {
  try {
    loadingCharts.value = true;

    const response = await getCodebaseComplianceDetail(since, until);
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
    title="Compliance Detail"
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

      <h3 class="mb-4 mt-10 text-xl font-semibold md:mt-0">Code Security</h3>
      <div>
        <p v-if="!modules?.Compliance?.code_security?.connected" class="mb-10 mt-5">
          Please
          <a href="/settings/connections/" class="font-semibold text-blue">connect your code security tool</a> to start
          gathering data.
        </p>
        <p v-else-if="!hasSnykData" class="mb-10 mt-5">We are still fetching data from Snyk, please come back later.</p>
        <div v-else class="mb-10 mt-5 grid gap-x-5 gap-y-10 md:grid-cols-3">
          <div v-if="chartSnykIssuesSast" class="md:col-span-2">
            <StackedBarChart
              id="snyk-sast"
              title="Code Security: In-File Security warnings by severity"
              :colors="SEVERITY_THREE_COLORS"
              :data="chartSnykIssuesSast"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartSnykIssuesSast && insightHighSast" class="md:mt-9">
            <InsightTextWarningsBenchmark :insight="insightHighSast" warning-type="in-file security" />
          </div>
          <div v-if="chartSnykIssuesCve" class="md:col-span-2">
            <StackedBarChart
              id="snyk-cve"
              title="Code Security: Third-Party Security warnings (CVEs) by severity"
              :colors="SEVERITY_THREE_COLORS"
              :data="chartSnykIssuesCve"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div v-if="chartSnykIssuesCve && insightHighCve" class="md:mt-9">
            <InsightTextWarningsBenchmark :insight="insightHighCve" warning-type="CVEs" />
          </div>
        </div>
      </div>

      <h3 class="mb-4 mt-10 text-xl font-semibold">Cyber Security</h3>
      <div>
        <p v-if="!modules?.Compliance?.cyber_security?.connected" class="mb-10 mt-5">
          Please
          <a href="/settings/connections/" class="font-semibold text-blue">connect your cyber security tool</a> to start
          gathering data.
        </p>
        <p v-else-if="!hasCyberSecurityData" class="mb-10 mt-5">
          We are still fetching data from iRADAR, please come back later.
        </p>
        <div v-else class="mb-10 mt-5 grid gap-x-5 gap-y-10 md:grid-cols-3">
          <div v-if="chartIRadarSubmodulesWithRisk" class="md:col-span-2">
            <StackedBarChart
              id="iradar-submodules-risk"
              title="Cyber Security: Number of Sub-Modules with Risk"
              :data="chartIRadarSubmodulesWithRisk"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
          <div class="md:mt-9">
            <CyberSecuritySubmodulesText v-if="iradarSubmodulesDifference" :submodules="iradarSubmodulesDifference" />
          </div>
          <div v-if="chartIRadarIssuesCve" class="md:col-span-2">
            <StackedBarChart
              id="iradar-cve"
              title="Cyber Security: Externally-Detectable CVEs"
              :colors="SEVERITY_THREE_COLORS"
              :data="chartIRadarIssuesCve"
              :loading="loadingCharts"
              :showTotals="true"
              tooltipSuffix=""
            />
          </div>
        </div>
      </div>

      <h3 class="mb-4 mt-10 text-xl font-semibold">Open Source</h3>
      <div>
        <p v-if="!modules?.Compliance?.open_source?.connected" class="mb-10 mt-5">
          Please <a href="/settings/connections/" class="font-semibold text-blue">connect your open source tool</a> to
          start gathering data.
        </p>
        <p v-else-if="!chartSnykIssuesLicense" class="mb-10 mt-5">
          We are still fetching data from Snyk, please come back later.
        </p>
        <div v-else class="mb-10 mt-5 grid gap-x-5 gap-y-10 md:grid-cols-3">
          <div v-if="chartSnykIssuesLicense" class="md:col-span-2">
            <StackedBarChart
              id="snyk-license"
              title="Open Source: License issues"
              :colors="SEVERITY_FOUR_COLORS"
              :data="chartSnykIssuesLicense"
              :loading="loadingCharts"
              tooltipSuffix=""
            />
          </div>
        </div>
      </div>

      <NavigateButtons exclude="compliance-detail" />
    </div>
  </div>
</template>
