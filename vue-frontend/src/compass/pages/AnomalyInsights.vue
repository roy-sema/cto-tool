<script setup lang="ts">
import MultiSelectWithButtons from "@/aicm/components/common/MultiSelectWithButtons.vue";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";

import { getAnomalyInsightsData } from "@/compass/helpers/api";
import type { AnomalyInsightsFilters, AnomalyInsightsItem } from "@/compass/helpers/api.d";
import {
  ArrowsUpDownIcon,
  BarsArrowDownIcon,
  BarsArrowUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { computed, onMounted, ref } from "vue";

const loading = ref(true);
const anomalies = ref<AnomalyInsightsItem[]>([]);
const totalCount = ref(0);
const currentPage = ref(1);
const totalPages = ref(0);

const filters = ref<AnomalyInsightsFilters>({});

const toDate = new Date();
const fromDate = new Date();
fromDate.setDate(toDate.getDate() - 14);

const date = ref<[Date, Date]>([fromDate, toDate]);

const resetDates = () => {
  filters.value.date_from = fromDate.toISOString();
  filters.value.date_to = toDate.toISOString();
  date.value = [fromDate, toDate];
};
resetDates();

const availableAnomalyTypes = ref<string[]>([]);
const availableSignificanceScores = ref<string[]>([]);
const availableRepositoryNames = ref<string[]>([]);
const availableProjectNames = ref<string[]>([]);
const availableCategories = ref<string[]>([]);

const anomalyTypeOptions = computed(() => availableAnomalyTypes.value.map((type) => ({ label: type, value: type })));

const significanceScoreOptions = computed(() =>
  availableSignificanceScores.value.map((score) => ({ label: score, value: score })),
);

const repositoryNameOptions = computed(() =>
  availableRepositoryNames.value.map((repo) => ({ label: repo, value: repo })),
);

const projectNameOptions = computed(() =>
  availableProjectNames.value.map((project) => ({ label: project, value: project })),
);

const categoryOptions = computed(() =>
  availableCategories.value.map((cat) => ({ label: getCategoryLabel(cat), value: cat })),
);

const loadData = async (page: number = 1) => {
  try {
    loading.value = true;

    const response = await getAnomalyInsightsData(filters.value, page);

    anomalies.value = response.results;
    totalCount.value = response.count;
    currentPage.value = response.current_page;
    totalPages.value = response.total_pages;

    availableAnomalyTypes.value = response.filter_options.anomaly_types;
    availableSignificanceScores.value = response.filter_options.significance_scores.map((score) => score.toString());
    availableRepositoryNames.value = response.filter_options.repository_names;
    availableProjectNames.value = response.filter_options.project_names;
    availableCategories.value = response.filter_options.categories || [];
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const applyFilters = () => {
  currentPage.value = 1;
  loadData();
};

const clearAllFilters = () => {
  filters.value = {};
  resetDates();
  currentPage.value = 1;
  loadData();
};

const getSortIcon = (field: string) => {
  if (filters.value.sort_by !== field) {
    return ArrowsUpDownIcon; // Default sort icon when not sorted
  }
  return filters.value.sort_order === "asc" ? BarsArrowUpIcon : BarsArrowDownIcon;
};

const onSort = (event: any) => {
  const sortStates: ("asc" | "desc" | undefined)[] = ["asc", "desc", undefined];
  const currentOrder = filters.value.sort_by === event.field ? filters.value.sort_order : undefined;
  const nextOrder =
    sortStates[(sortStates.indexOf(currentOrder as "asc" | "desc" | undefined) + 1) % sortStates.length];
  filters.value.sort_by = nextOrder ? event.field : undefined;
  filters.value.sort_order = nextOrder;
  currentPage.value = 1;
  loadData();
};

const onPageChange = (page: number) => {
  loadData(page);
};

const smartDateHandler = async (value: string[]) => {
  if (value && value.length === 2) {
    filters.value.date_from = value[0];
    filters.value.date_to = value[1];
    date.value = [new Date(value[0]), new Date(value[1])];
    applyFilters();
  }
};

const getConfidenceLevelColor = (confidenceLevel: string): "success" | "warning" | "danger" => {
  const colorMap: Record<string, "success" | "warning" | "danger"> = {
    "High Confidence": "success",
    "Medium Confidence": "warning",
    "Low Confidence": "danger",
  };
  return colorMap[confidenceLevel] || "warning";
};

const getSignificanceScoreColor = (score: number): "success" | "warning" | "danger" => {
  if (score >= 7) return "danger";
  if (score >= 4) return "warning";
  return "success";
};

const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString();
};

const truncateText = (text: string, maxLength: number = 100): string => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
};

// Mapping from enum values to human-readable labels
const CATEGORY_LABELS: Record<string, string> = {
  timeline_impact: "Timeline Impact",
  quality_impact: "Quality Impact",
  scope_impact: "Scope Impact",
  resource_impact: "Resource Impact",
  technical_impact: "Technical Impact",
  feature_addition: "Feature Addition",
  feature_enhancement: "Feature Enhancement",
  other: "Other",
};

const CONFIDENCE_LEVEL_LABELS: Record<string, string> = {
  High: "High Confidence",
  Medium: "Medium Confidence",
  Low: "Low Confidence",
};

// Helper to get human-readable label for confidence level
const getConfidenceLevelLabel = (level: string): string => {
  return CONFIDENCE_LEVEL_LABELS[level] || level;
};

const confidenceLevelOptions = [
  { label: getConfidenceLevelLabel("High"), value: "High" },
  { label: getConfidenceLevelLabel("Medium"), value: "Medium" },
  { label: getConfidenceLevelLabel("Low"), value: "Low" },
];

// Helper to get human-readable label for category
const getCategoryLabel = (category: string): string => {
  return CATEGORY_LABELS[category] || category;
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader title="Anomaly Insights" :updatedAt="null" />

  <div class="sip xxl:w-full max-w-screen-xxl mx-auto mt-5 flex w-screen flex-col gap-4 px-4 lg:w-[78vw] xl:w-[80vw]">
    <Card>
      <template #content>
        <div class="mb-4">
          <div class="mb-3 flex flex-col items-center justify-between sm:flex-row">
            <h3 class="text-lg font-semibold">Filters</h3>
            <div class="flex w-full flex-col items-center gap-3 sm:flex-row">
              <div class="flex w-full items-center justify-between gap-3 sm:justify-end">
                <div class="text-base text-gray-600">Showing {{ totalCount }} anomalies</div>
                <RangeDatePicker :date="date" class="w-full" @update:date="smartDateHandler" />
              </div>
              <Button
                label="Clear All Filters"
                severity="warning"
                size="small"
                class="w-full min-w-max sm:w-auto"
                @click="clearAllFilters"
              />
            </div>
          </div>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <label class="mb-2 block text-sm font-medium">Anomaly Types</label>
              <MultiSelectWithButtons
                v-model="filters.anomaly_types"
                :options="anomalyTypeOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Select anomaly types"
                class="!w-full"
                @change="applyFilters"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium">Significance Scores</label>
              <MultiSelectWithButtons
                v-model="filters.significance_scores"
                :options="significanceScoreOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Select significance scores"
                class="!w-full"
                @change="applyFilters"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium">Repositories</label>
              <MultiSelectWithButtons
                v-model="filters.repository_names"
                :options="repositoryNameOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Select repositories"
                class="!w-full"
                @change="applyFilters"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium">Projects</label>
              <MultiSelectWithButtons
                v-model="filters.project_names"
                :options="projectNameOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Select projects"
                class="!w-full"
                @change="applyFilters"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium">Category</label>
              <MultiSelectWithButtons
                v-model="filters.categories"
                :options="categoryOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Select categories"
                class="!w-full"
                @change="applyFilters"
              />
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium">Confidence Level</label>
              <MultiSelectWithButtons
                v-model="filters.confidence_levels"
                :options="confidenceLevelOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Select confidence levels"
                class="!w-full"
                @change="applyFilters"
              />
            </div>
          </div>
        </div>
      </template>
    </Card>

    <!-- Data Table Card -->
    <Card>
      <template #content>
        <div v-if="loading" class="flex justify-center py-8">
          <ProgressSpinner class="!size-10" />
        </div>

        <div v-else-if="anomalies.length === 0" class="py-8 text-center text-gray-500">
          No anomalies found matching the selected filters.
        </div>

        <div v-else class="w-full overflow-x-auto">
          <DataTable
            :value="anomalies"
            class="min-w-max"
            scrollable
            :row-class="() => 'hover:bg-gray-50 dark:hover:bg-sky-950'"
          >
            <Column field="anomaly_id" header="Anomaly ID">
              <template #body="{ data }">
                <span class="block text-center font-mono text-sm text-blue">
                  {{ data.anomaly_id }}
                </span>
              </template>
            </Column>

            <Column field="title" header="Title">
              <template #body="{ data }">
                <span class="block max-w-80 truncate text-left" :title="data.title">
                  {{ truncateText(data.title, 50) }}
                </span>
              </template>
            </Column>

            <Column field="anomaly_type">
              <template #header>
                <div
                  class="flex cursor-pointer items-center justify-center gap-1"
                  @click="onSort({ field: 'anomaly_type' })"
                >
                  <span>Type</span>
                  <component :is="getSortIcon('anomaly_type')" class="size-4" />
                </div>
              </template>
              <template #body="{ data }">
                <div class="flex justify-center">
                  <Tag :value="data.anomaly_type" severity="info" />
                </div>
              </template>
            </Column>

            <Column field="category">
              <template #header>
                <div
                  class="flex cursor-pointer items-center justify-center gap-1"
                  @click="onSort({ field: 'category' })"
                >
                  <span>Category</span>
                  <component :is="getSortIcon('category')" class="size-4" />
                </div>
              </template>
              <template #body="{ data }">
                <div class="flex">
                  <Tag :value="getCategoryLabel(data.category)" severity="secondary" />
                </div>
              </template>
            </Column>

            <Column field="significance_score">
              <template #header>
                <div
                  class="flex cursor-pointer items-center justify-center gap-1"
                  @click="onSort({ field: 'significance_score' })"
                >
                  <span>Significance</span>
                  <component :is="getSortIcon('significance_score')" class="size-4" />
                </div>
              </template>
              <template #body="{ data }">
                <div class="flex justify-center">
                  <Tag
                    :value="data.significance_score.toString()"
                    :severity="getSignificanceScoreColor(data.significance_score)"
                  />
                </div>
              </template>
            </Column>

            <Column field="confidence_level">
              <template #header>
                <div
                  class="flex cursor-pointer items-center justify-center gap-1"
                  @click="onSort({ field: 'confidence_level' })"
                >
                  <span>Confidence Level</span>
                  <component :is="getSortIcon('confidence_level')" class="size-4" />
                </div>
              </template>
              <template #body="{ data }">
                <div class="flex justify-center">
                  <Tag
                    :value="getConfidenceLevelLabel(data.confidence_level)"
                    :severity="getConfidenceLevelColor(getConfidenceLevelLabel(data.confidence_level))"
                  />
                </div>
              </template>
            </Column>

            <Column field="repository_name" header="Repository">
              <template #body="{ data }">
                <span v-if="data.repository_name" class="block text-center text-sm">
                  {{ data.repository_name }}
                </span>
                <span v-else class="block text-center text-sm text-gray-400">-</span>
              </template>
            </Column>

            <Column field="project_name" header="Project">
              <template #body="{ data }">
                <span v-if="data.project_name" class="block text-center text-sm">
                  {{ data.project_name }}
                </span>
                <span v-else class="block text-center text-sm text-gray-400">-</span>
              </template>
            </Column>

            <Column field="created_at">
              <template #header>
                <div
                  class="flex cursor-pointer items-center justify-center gap-1"
                  @click="onSort({ field: 'created_at' })"
                >
                  <span>Creation date</span>
                  <component :is="getSortIcon('created_at')" class="size-4" />
                </div>
              </template>
              <template #body="{ data }">
                <span class="block text-center text-sm">
                  {{ formatDate(data.created_at) }}
                </span>
              </template>
            </Column>
          </DataTable>

          <!-- Pagination -->
          <div v-if="totalPages > 1" class="mt-4 flex justify-center">
            <div class="flex items-center gap-2">
              <Button :disabled="currentPage === 1" @click="onPageChange(currentPage - 1)">
                <template #icon>
                  <ChevronLeftIcon class="size-4" />
                </template>
              </Button>
              <span class="text-sm"> Page {{ currentPage }} of {{ totalPages }} </span>
              <Button :disabled="currentPage === totalPages" @click="onPageChange(currentPage + 1)">
                <template #icon>
                  <ChevronRightIcon class="size-4" />
                </template>
              </Button>
            </div>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>
