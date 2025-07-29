<script setup lang="ts">
import MultiSelectWithButtons from "@/aicm/components/common/MultiSelectWithButtons.vue";
import type { IntegrationStatusMap } from "@/common/api.d";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import CodeHighlight from "@/compass/components/CodeHighlight.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import HorizontalStacked100BarChart from "@/compass/components/HorizontalStacked100BarChart.vue";
import {
  // generateDashboardInsights,
  getDashboardData,
} from "@/compass/helpers/api";
import {
  type Anomaly,
  type Chart,
  type GroupedAnomaly,
  type GroupedJustification,
  type Product,
} from "@/compass/helpers/api.d";
import {
  //  SparklesIcon,
  InformationCircleIcon,
} from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { computed, onMounted, ref } from "vue";

const colors = [
  "#0081A7",
  "#75F4F4",
  "#E80673",
  "#29FFC6",
  "#FF5733",
  "#C70039",
  "#900C3F",
  "#581845",
  "#FFC300",
  "#DAF7A6",
];

const activeInsight = ref("");
const chart = ref<Chart>();
const date = ref<[Date, Date] | null>(null);
const dateRange = ref<[Date, Date] | null>(null);
const defaultTimeWindowDays = ref();
const groupedJustifications = ref<GroupedJustification>();
const integrations = ref<IntegrationStatusMap>();
const anomalyInsights = ref<GroupedAnomaly>({});
// const isGeneratingInsights = ref(false);
const loading = ref(true);
const loadingUpdate = ref(false);
const orgFirstDate = ref();
const products = ref<Product[]>();
const repositoryGroupsUrl = ref("");
const selectedLayers = ref();
const selectedProducts = ref();
const updatedAt = ref();

// let intervalId: ReturnType<typeof setInterval>;

const layers = computed(() => chart.value?.series?.map((series) => series.name) ?? []);

const numAnomalyInsights = computed(() => (anomalyInsights.value ? Object.keys(anomalyInsights.value).length : 0));

const numGroupedJustificationsProducts = computed(() => Object.keys(groupedJustifications.value || {}).length);

const selectedProductsIndexes = computed(() => {
  return selectedProducts.value.map((id: string) => products.value?.findIndex((product) => product.id === id));
});

const filteredChart = computed(() => {
  if (!chart.value || !chart.value.categories || !chart.value.series) return { no_data: true };

  const categories = chart.value.categories.filter((_category, index) => selectedProductsIndexes.value.includes(index));
  const series = chart.value.series.map((series) => {
    return {
      ...series,
      data: series.data.filter((_, index) => selectedProductsIndexes.value.includes(index)),
    };
  });

  return { categories, series };
});

// const insightsNotGenerated = computed(() => groupedJustifications.value === null);

const loadData = async (since?: string, until?: string) => {
  try {
    if (since && until) {
      loadingUpdate.value = true;
    } else {
      loading.value = true;
    }

    // isGeneratingInsights.value = false;

    const response = await getDashboardData(since, until);
    chart.value = response.chart;
    products.value = response.products;
    updatedAt.value = response.updated_at;
    orgFirstDate.value = response.org_first_date;
    integrations.value = response.integrations;
    anomalyInsights.value = response.anomaly_insights;
    groupedJustifications.value = response.grouped_justifications;
    defaultTimeWindowDays.value = response.default_time_window_days;
    repositoryGroupsUrl.value = response.repository_groups_url;

    selectedLayers.value = layers.value;
    selectedProducts.value = products.value.map((product) => product.id);

    const [fromDate, toDate] = response.date_range;
    dateRange.value = [new Date(fromDate * 1000), new Date(toDate * 1000)];
    date.value = [new Date(fromDate * 1000), new Date(toDate * 1000)];
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
    loadingUpdate.value = false;
  }
};

// TODO remove or bring this back when a product decision is made
// const generateInsights = async () => {
//   if (!dateRange.value) return;

//   const [since, until] = dateRange.value;
//   if (!since || !until) return;

//   try {
//     // isGeneratingInsights.value = true;
//     await generateDashboardInsights(since.toISOString(), until.toISOString());
//     intervalId = setInterval(pollInsights, 5000);
//   } catch (error) {
//     Sentry.captureException(error);
//     // isGeneratingInsights.value = false;
//   }
// };

// const pollInsights = async () => {
//   if (!dateRange.value) return;

//   const [since, until] = dateRange.value;
//   if (!since || !until) return;

//   try {
//     const response = await getDashboardData(since.toISOString(), until.toISOString());
//     if (response.justifications !== null) {
//       groupedJustifications.value = response.grouped_justifications;
//       // isGeneratingInsights.value = false;
//       clearInterval(intervalId);
//     }
//   } catch (error) {
//     Sentry.captureException(error);
//   }
// };

const smartDateHandler = async (value: string[]) => {
  if (value && value.length === 2) {
    // clearInterval(intervalId);
    loadData(value[0], value[1]);
  }
};

const getProductNameForId = (id: string | number) => products.value?.find((product) => product.id == id)?.name;

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader
    title="Development Activity"
    :updatedAt="updatedAt"
    :integrations="integrations"
    :loading="loading"
    :dateRange="dateRange"
  />

  <div class="flex flex-col justify-between gap-5 px-4 py-5 lg:px-6 xl:flex-row">
    <div class="shrink-0 xl:w-2/3">
      <Panel>
        <template #header>
          <div class="flex w-full flex-col justify-between md:flex-row">
            <h2 class="text-lg font-semibold">Development Activity Type by Product</h2>
            <a class="content-center text-sm text-blue" :href="repositoryGroupsUrl">
              Set Products (Repository Groups) here
            </a>
          </div>
        </template>

        <div v-if="loading" class="flex items-center justify-center">
          <ProgressSpinner />
        </div>
        <div v-else-if="!products?.length">
          <p>There's no data to report.</p>
        </div>
        <div v-else>
          <div class="flex flex-col justify-between md:flex-row md:gap-5">
            <div>
              <div class="mb-1 text-sm font-semibold">Select products</div>
              <MultiSelectWithButtons
                v-model="selectedProducts"
                :options="products"
                optionLabel="name"
                optionValue="id"
                placeholder="Select Products"
                :maxSelectedLabels="3"
                :showToggleAll="false"
                class="w-full md:w-80"
                size="small"
              />
            </div>
            <div class="content-end">
              <RangeDatePicker
                class="!w-full md:!w-56"
                :date="date"
                :firstDate="orgFirstDate"
                @update:date="smartDateHandler"
              />
            </div>
          </div>

          <HorizontalStacked100BarChart
            id="development-activity-type-by-product"
            :colors="colors"
            :data="filteredChart"
            :loading="loadingUpdate"
          />
        </div>
      </Panel>
    </div>

    <div class="grow">
      <h2 class="mb-2 text-xl font-bold">Insights</h2>

      <Panel collapsed toggleable class="mb-5">
        <template #header>
          <div class="flex w-full justify-between">
            <div class="flex items-center gap-2">
              <h3 class="text-md font-semibold">Anomaly Insights ({{ numAnomalyInsights }})</h3>
              <InformationCircleIcon
                v-tooltip.top="{ value: 'Last 14 days', pt: { text: 'text-sm' } }"
                class="size-4 cursor-pointer text-blue"
              />
            </div>
            <Tag severity="info" value="AI" class="size-6 self-center !text-xs !font-normal" />
          </div>
        </template>

        <div v-if="loading || loadingUpdate" class="flex items-center justify-center">
          <ProgressSpinner />
        </div>
        <div v-else-if="!numAnomalyInsights">
          <div class="flex items-center gap-2">
            <InformationCircleIcon class="size-4 text-blue" />
            <div class="text-sm">Not enough data</div>
          </div>
        </div>
        <div v-else>
          <Accordion multiple class="insights">
            <AccordionPanel
              v-for="(repos, repoGroupName) in anomalyInsights"
              :key="repoGroupName"
              :value="repoGroupName"
              :pt="{ root: 'last:!border-none' }"
            >
              <AccordionHeader>
                <div class="flex items-center gap-2">
                  <InformationCircleIcon class="size-4 text-blue" />
                  <div class="text-sm"><span class="text-gray-500">Repository Group:</span> {{ repoGroupName }}</div>
                </div>
              </AccordionHeader>
              <AccordionContent>
                <Accordion multiple>
                  <AccordionPanel v-for="(anomalies, repoName) in repos" :key="repoName" :value="repoName" class="pt-5">
                    <AccordionHeader>
                      <div class="text-sm font-medium">
                        <span class="text-gray-500">Repository:</span> {{ repoName }}
                      </div>
                    </AccordionHeader>
                    <AccordionContent>
                      <div
                        v-for="(anomaly, index) in anomalies as Anomaly[]"
                        :key="index"
                        class="break-word-all m-0 break-words text-sm"
                      >
                        <p class="text-sm text-gray-500">Overview:</p>
                        <p class="whitespace-pre-line">{{ anomaly.insight }}</p>
                        <div v-if="anomaly.category">
                          <p class="mt-2 text-sm text-gray-500">Category:</p>
                          <p class="whitespace-pre-line">{{ anomaly.category }}</p>
                        </div>
                        <div v-if="anomaly.significance_score">
                          <p class="mt-2 text-sm text-gray-500">Significance Score:</p>
                          <p class="whitespace-pre-line">{{ anomaly.significance_score }}</p>
                        </div>
                        <div v-if="anomaly.confidence_level">
                          <p class="mt-2 text-sm text-gray-500">Confidence Level:</p>
                          <p class="whitespace-pre-line">{{ anomaly.confidence_level }}</p>
                        </div>
                        <div v-if="anomaly.evidence">
                          <p class="mt-2 text-sm text-gray-500">Evidence:</p>
                          <p class="whitespace-pre-line">{{ anomaly.evidence }}</p>
                        </div>
                        <div v-if="anomaly.resolution">
                          <p class="mt-2 text-sm text-gray-500">Potential Next Steps:</p>
                          <p class="whitespace-pre-line">{{ anomaly.resolution }}</p>
                        </div>
                        <div v-if="anomaly.messages">
                          <p class="mt-4 text-sm text-gray-500">SkipAMeeting:</p>
                          <div v-for="(message, msgIdx) in anomaly.messages" :key="msgIdx">
                            <p class="mt-2 text-sm text-gray-500">Audience: {{ message.audience }}</p>
                            <p class="whitespace-pre-line">
                              {{ message.message_for_audience }}
                            </p>
                          </div>
                        </div>
                        <Divider v-if="index !== anomalies.length - 1" />
                      </div>
                    </AccordionContent>
                  </AccordionPanel>
                </Accordion>
              </AccordionContent>
            </AccordionPanel>
          </Accordion>
        </div>
      </Panel>

      <Panel collapsed toggleable>
        <template #header>
          <div class="flex w-full justify-between">
            <div class="flex items-center gap-2">
              <h3 class="text-md font-semibold">Summary insights ({{ numGroupedJustificationsProducts }})</h3>
              <InformationCircleIcon
                v-tooltip.top="{ value: 'Last 14 days', pt: { text: 'text-sm' } }"
                class="size-4 cursor-pointer text-blue"
              />
            </div>
            <Tag severity="info" value="AI" class="size-6 self-center !text-xs !font-normal" />
          </div>
        </template>

        <div v-if="loading || loadingUpdate" class="flex items-center justify-center">
          <ProgressSpinner />
        </div>
        <!-- TODO remove or bring this back when a product decision is made -->
        <!-- <div v-else-if="insightsNotGenerated && !filteredChart.no_data">
          <div class="mb-3 text-sm">Generate the insights for the selected period:</div>
          <Button
            :label="isGeneratingInsights ? 'Generating insights' : 'Generate insights'"
            :loading="isGeneratingInsights"
            severity="contrast"
            size="small"
            variant="outlined"
            class="xl:w-full"
            @click="generateInsights"
          >
            <template #icon>
              <SparklesIcon class="size-4" />
            </template>
          </Button>
        </div> -->
        <div v-else-if="!numGroupedJustificationsProducts">
          <div class="flex items-center gap-2">
            <InformationCircleIcon class="size-4 text-blue" />
            <div class="text-sm">Not enough data</div>
          </div>
          <p class="break-words text-sm font-normal italic text-muted-color">There are no insights.</p>
        </div>
        <div v-else>
          <Accordion v-model:value="activeInsight" class="insights">
            <AccordionPanel
              v-for="(justifications, groupId) in groupedJustifications"
              :value="groupId"
              :pt="{ root: 'last:!border-none' }"
            >
              <AccordionHeader>
                <div>
                  <div class="flex items-center gap-2">
                    <InformationCircleIcon class="size-4 text-blue" />
                    <div class="text-sm">{{ getProductNameForId(groupId) }}</div>
                  </div>
                </div>
              </AccordionHeader>
              <AccordionContent>
                <Accordion class="insights">
                  <AccordionPanel
                    v-for="(justification, category) in justifications"
                    :value="category"
                    :pt="{ root: 'last:!border-none' }"
                  >
                    <AccordionHeader>
                      <div>
                        <div class="flex items-center gap-2">
                          <div class="text-sm">{{ category }}</div>
                        </div>
                        <p class="whitespace-pre-line break-words text-sm font-normal">
                          <CodeHighlight :content="justification.justification" />
                        </p>
                        <div class="text-right">
                          <Button v-show="activeInsight !== category" label="Read more" size="small" link />
                        </div>
                      </div>
                    </AccordionHeader>
                    <AccordionContent>
                      <p class="m-0 whitespace-pre-line break-words text-sm">
                        <CodeHighlight :content="justification.examples" />
                      </p>
                    </AccordionContent>
                  </AccordionPanel>
                </Accordion>
              </AccordionContent>
            </AccordionPanel>
          </Accordion>
        </div>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
:deep(.p-message-content) {
  @apply block text-center;
}

:deep(.chart-header) {
  @apply relative;
}

:deep(.chart-spinner-container) {
  @apply absolute right-8 top-3.5;
}
</style>
