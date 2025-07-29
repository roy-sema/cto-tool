<script setup lang="ts">
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import TicketCompletenessTrendChart from "@/compass/components/TicketCompletenessTrendChart.vue";
import TicketDetailModal from "@/compass/components/TicketDetailModal.vue";

import {
  getTicketCompletenessData,
  getTicketCompletenessStatistics,
  getTicketCompletenessTrendChart,
} from "@/compass/helpers/api";
import type {
  TicketCompletenessFilters,
  TicketCompletenessItem,
  TicketCompletenessStatisticsResponse,
  TicketCompletenessTrendChartResponse,
} from "@/compass/helpers/api.d";
import {
  ArrowsUpDownIcon,
  BarsArrowDownIcon,
  BarsArrowUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  InformationCircleIcon,
} from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { LineChart, Ticket, TrendingDown, TrendingUp, TriangleAlert } from "lucide-vue-next";
import Select from "primevue/select";
import { computed, onMounted, ref } from "vue";

const loading = ref(true);
const tickets = ref<TicketCompletenessItem[]>([]);
const totalCount = ref(0);

// Pagination state
const currentPage = ref(1);
const totalPages = ref(0);

const statistics = ref<TicketCompletenessStatisticsResponse | null>(null);
const statisticsLoading = ref(true);

// Trend chart data
const trendChartData = ref<TicketCompletenessTrendChartResponse | null>(null);
const trendChartLoading = ref(true);

// Date picker state
// Initialize with last 14 days
const toDate = new Date();
const fromDate = new Date();
fromDate.setDate(toDate.getDate() - 14);

const date = ref<[Date, Date]>([fromDate, toDate]);

// Sorting state (reuse filters)
const filters = ref<TicketCompletenessFilters>({});

// Computed properties for delta calculations
const currentStats = computed(() => statistics.value?.latest || null);
const historicalStats = computed(() => statistics.value?.historical || null);

const avgScoreDelta = computed(() => {
  if (!currentStats.value || !historicalStats.value) return null;
  return currentStats.value.avg_completeness_score - historicalStats.value.avg_completeness_score;
});

const activeTicketsDelta = computed(() => {
  if (!currentStats.value || !historicalStats.value) return null;
  return currentStats.value.active_tickets_count - historicalStats.value.active_tickets_count;
});

const lowScoreUnderwayDelta = computed(() => {
  if (!currentStats.value || !historicalStats.value) return null;
  return currentStats.value.low_score_underway_count - historicalStats.value.low_score_underway_count;
});

const getDeltaDisplay = (delta: number | null, isPercentage = false) => {
  if (!delta) return "No change";

  const sign = delta > 0 ? "+" : "-";
  const value = Math.abs(delta);
  if (isPercentage) {
    return `${sign}${value.toFixed(1)}`;
  }

  return `${sign}${value}`;
};

const getDeltaIcon = (delta: number | null) => {
  if (!delta) return null;
  return delta > 0 ? TrendingUp : TrendingDown;
};

const isInitialScoreUnderwayActive = ref(false);

const availableLlmCategories = ref<string[]>([]);
const availableProjectKeys = ref<string[]>([]);
const availableStages = ref<string[]>([]);

const selectedStatisticsProject = ref<string | null>(null);

// Modal state
const modalVisible = ref(false);
const selectedTicketId = ref<string | null>(null);

const llmCategoryOptions = computed(() => [
  { label: "All Categories", value: null },
  ...availableLlmCategories.value.map((category) => ({ label: category, value: category })),
]);

const projectKeyOptions = computed(() => [
  { label: "All Projects", value: null },
  ...availableProjectKeys.value.map((project) => ({ label: project, value: project })),
]);

const stageOptions = computed(() => [
  { label: "All Stages", value: null },
  ...availableStages.value.map((stage) => ({ label: stage, value: stage })),
]);

const isProjectDropdownDisabled = computed(() => selectedStatisticsProject.value !== null);

const loadStatistics = async () => {
  try {
    statisticsLoading.value = true;
    const response = await getTicketCompletenessStatistics(selectedStatisticsProject.value || undefined);
    statistics.value = response;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    statisticsLoading.value = false;
  }
};

const loadTrendChartData = async (since: Date, until: Date) => {
  try {
    trendChartLoading.value = true;
    const response = await getTicketCompletenessTrendChart(
      since.toISOString().split("T")[0],
      until.toISOString().split("T")[0],
      selectedStatisticsProject.value || undefined,
    );
    trendChartData.value = response;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    trendChartLoading.value = false;
  }
};

const loadData = async (page: number = 1) => {
  try {
    loading.value = true;

    const response = await getTicketCompletenessData(filters.value, page);
    tickets.value = response.results;
    totalCount.value = response.count;
    currentPage.value = response.current_page;
    totalPages.value = response.total_pages;

    availableLlmCategories.value = response.filter_options.llm_categories;
    availableProjectKeys.value = response.filter_options.project_keys;
    availableStages.value = response.filter_options.stages;

    // Reload statistics to get project-specific data if a project is selected
    if (selectedStatisticsProject.value) {
      loadStatistics();
    }
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const applyFilters = () => {
  currentPage.value = 1;
  loadData(1);
};

const onPageChange = (page: number) => {
  loadData(page);
};

// Sorting logic (date and others)
const getSortIcon = (field: string) => {
  if (filters.value.sort_by !== field) {
    return ArrowsUpDownIcon;
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
  loadData(1);
};

const originalStage = ref<string | undefined>(undefined);

const applyInitialScoreUnderwayFilter = () => {
  if (isInitialScoreUnderwayActive.value) {
    // Restore original values
    filters.value.stage = originalStage.value;
    filters.value.quality_category = undefined;
    isInitialScoreUnderwayActive.value = false;
  } else {
    // Store current values and apply filter
    originalStage.value = filters.value.stage;
    filters.value.stage = "Underway";
    filters.value.quality_category = "Initial";
    isInitialScoreUnderwayActive.value = true;
  }
  loadData();
};

const selectStatisticsProject = (projectKey: string | null) => {
  selectedStatisticsProject.value = projectKey;

  // Auto-select project for filtering when a specific project is chosen
  if (projectKey) {
    filters.value.project_key = projectKey;
  } else {
    // When switching back to "Organization Overview", clear the project filter
    filters.value.project_key = undefined;
  }

  loadStatistics();
  loadTrendChartData(date.value[0], date.value[1]);
  loadData();
};

const smartDateHandler = async (value: string[]) => {
  if (value && value.length === 2) {
    loadTrendChartData(new Date(value[0]), new Date(value[1]));
  }
};

const getProgressBarColor = (qualityCategory: string): "red" | "orange" | "yellow" | "green" | "blue" => {
  const colorMap: Record<string, "red" | "orange" | "yellow" | "green" | "blue"> = {
    Initial: "red",
    Emerging: "orange",
    Mature: "yellow",
    Advanced: "green",
  };
  return colorMap[qualityCategory] || "blue";
};

const openTicketModal = (ticketId: string) => {
  selectedTicketId.value = ticketId;
  modalVisible.value = true;
};

onMounted(() => {
  loadStatistics();
  loadTrendChartData(date.value[0], date.value[1]);
  loadData();
});
</script>

<template>
  <PageHeader title="Ticket Completeness" :updatedAt="null" />

  <div class="sip mx-auto mt-5 flex max-w-screen-xl flex-col gap-4 px-4">
    <Card v-if="availableProjectKeys.length > 0">
      <template #content>
        <div class="flex flex-wrap gap-2">
          <Button
            :label="'Organization Overview'"
            :severity="selectedStatisticsProject === null ? 'primary' : 'secondary'"
            @click="selectStatisticsProject(null)"
          />
          <Button
            v-for="projectKey in availableProjectKeys"
            :key="projectKey"
            :label="`${projectKey} Project`"
            :severity="selectedStatisticsProject === projectKey ? 'primary' : 'secondary'"
            @click="selectStatisticsProject(projectKey)"
          />
        </div>
      </template>
    </Card>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Card>
        <template #content>
          <div class="relative">
            <div class="absolute right-0 top-0">
              <LineChart class="text-muted-foreground h-5 w-5" />
            </div>
            <div class="text-left">
              <div class="text-muted-foreground mb-5 text-sm">Avg TCS Score</div>
              <div v-if="statisticsLoading" class="flex justify-center">
                <ProgressSpinner class="!size-6" />
              </div>
              <div v-else class="text-foreground text-3xl font-bold">
                {{ currentStats?.avg_completeness_score || 0 }}
              </div>
              <div v-if="avgScoreDelta !== null" class="mt-1 flex items-center gap-1 text-sm">
                <component :is="getDeltaIcon(avgScoreDelta)" class="size-4 text-gray-500" />
                <span class="text-gray-500"> {{ getDeltaDisplay(avgScoreDelta, true) }} vs last week </span>
              </div>
            </div>
          </div>
        </template>
      </Card>

      <Card>
        <template #content>
          <div class="relative">
            <div class="absolute right-0 top-0">
              <Ticket class="text-muted-foreground h-5 w-5" />
            </div>
            <div class="text-left">
              <div class="text-muted-foreground mb-5 flex items-center gap-1 text-sm">
                Active Tickets
                <InformationCircleIcon
                  v-tooltip.top="{
                    value: 'Excludes backlog and done tickets',
                    escape: false,
                    autoHide: false,
                    pt: { text: 'text-xs' },
                  }"
                  class="size-4 shrink-0 cursor-pointer text-blue"
                />
              </div>
              <div v-if="statisticsLoading" class="flex justify-center">
                <ProgressSpinner class="!size-6" />
              </div>
              <div v-else class="text-foreground text-3xl font-bold">
                {{ currentStats?.active_tickets_count || 0 }}
              </div>
              <div v-if="activeTicketsDelta !== null" class="mt-1 flex items-center gap-1 text-sm">
                <component :is="getDeltaIcon(activeTicketsDelta)" class="size-4 text-gray-500" />
                <span class="text-gray-500"> {{ getDeltaDisplay(activeTicketsDelta) }} from last week </span>
              </div>
            </div>
          </div>
        </template>
      </Card>

      <Card>
        <template #content>
          <div class="relative">
            <div class="absolute right-0 top-0">
              <TriangleAlert class="text-muted-foreground h-5 w-5" />
            </div>
            <div class="text-left">
              <div class="text-muted-foreground mb-5 flex items-center gap-1 text-sm">
                Initial Score Underway
                <InformationCircleIcon
                  v-tooltip.top="{
                    value: 'Excludes backlog and done tickets',
                    escape: false,
                    autoHide: false,
                    pt: { text: 'text-xs' },
                  }"
                  class="size-4 shrink-0 cursor-pointer text-blue"
                />
              </div>
              <div v-if="statisticsLoading" class="flex justify-center">
                <ProgressSpinner class="!size-6" />
              </div>
              <div v-else class="text-foreground text-3xl font-bold">
                {{ currentStats?.low_score_underway_count || 0 }}
              </div>
              <div v-if="lowScoreUnderwayDelta !== null" class="mt-1 flex items-center gap-1 text-sm">
                <component :is="getDeltaIcon(lowScoreUnderwayDelta)" class="size-4 text-gray-500" />
                <span class="text-gray-500"> {{ getDeltaDisplay(lowScoreUnderwayDelta) }} from last week </span>
              </div>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <Card>
      <template #content>
        <div class="mb-4 flex flex-col justify-between md:flex-row">
          <h3 class="text-lg font-semibold">Average Completeness Score Trend</h3>
          <div class="content-end">
            <RangeDatePicker class="!w-full md:!w-56" :date="date" @update:date="smartDateHandler" />
          </div>
        </div>
        <TicketCompletenessTrendChart
          id="ticket-completeness-trend"
          title=""
          :data="trendChartData"
          :loading="trendChartLoading"
          :height="300"
        />
      </template>
    </Card>

    <Card>
      <template #content>
        <div class="mb-4">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-lg font-semibold">Filters</h3>
            <div class="flex items-center gap-2.5">
              <div class="text-base text-gray-600">Showing {{ totalCount }} tickets</div>
              <Button
                :label="isInitialScoreUnderwayActive ? 'Clear Initial Score Filter' : 'Initial Score Underway'"
                :severity="isInitialScoreUnderwayActive ? 'secondary' : 'warning'"
                @click="applyInitialScoreUnderwayFilter"
              />
            </div>
          </div>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <label class="mb-2 block text-sm font-medium">Category</label>
              <div class="flex gap-2">
                <Select
                  v-model="filters.llm_category"
                  :options="llmCategoryOptions"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="All Categories"
                  class="flex-1"
                  @change="applyFilters"
                />
              </div>
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium">Project Key</label>
              <div class="flex gap-2">
                <Select
                  v-model="filters.project_key"
                  :options="projectKeyOptions"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="All Projects"
                  class="flex-1"
                  :disabled="isProjectDropdownDisabled"
                  @change="applyFilters"
                />
              </div>
              <div v-if="isProjectDropdownDisabled" class="mt-1 text-xs text-gray-500">
                Project filter is locked to "{{ selectedStatisticsProject }}" - switch to "Organization Overview" to
                change
              </div>
            </div>

            <div>
              <label class="mb-2 block text-sm font-medium">Stage</label>
              <div class="flex gap-2">
                <Select
                  v-model="filters.stage"
                  :options="stageOptions"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="All Stages"
                  class="flex-1"
                  @change="applyFilters"
                />
              </div>
            </div>
          </div>
        </div>
      </template>
    </Card>

    <Card>
      <template #content>
        <div v-if="loading" class="flex justify-center py-8">
          <ProgressSpinner class="!size-10" />
        </div>

        <div v-else-if="tickets.length === 0" class="py-8 text-center text-gray-500">
          No tickets found matching the selected filters.
        </div>

        <div v-else class="max-w-[90vw] lg:max-w-[72vw] xl:max-w-none">
          <DataTable
            :value="tickets"
            class="w-full"
            scrollable
            removableSort
            :row-class="() => 'cursor-pointer hover:bg-gray-50 dark:hover:bg-sky-950'"
            @row-click="(event) => openTicketModal(event.data.ticket_id)"
          >
            <Column field="ticket_id" header="Ticket ID" class="min-w-32">
              <template #body="{ data }">
                <span class="font-mono text-sm text-blue">
                  {{ data.ticket_id }}
                </span>
              </template>
            </Column>

            <Column field="name" header="Name" class="min-w-48">
              <template #body="{ data }">
                <span class="max-w-xs truncate text-left" :title="data.name">
                  {{ data.name.length > 50 ? data.name.substring(0, 50) + "..." : data.name }}
                </span>
              </template>
            </Column>

            <Column field="project_key" header="Project" class="min-w-24">
              <template #body="{ data }">
                <Tag :value="data.project_key" severity="info" />
              </template>
            </Column>

            <Column field="llm_category" header="Category" class="min-w-32">
              <template #body="{ data }">
                <Tag :value="data.llm_category" severity="secondary" />
              </template>
            </Column>

            <Column field="stage" header="Stage" class="min-w-32">
              <template #body="{ data }">
                <Tag :value="data.stage" severity="warning" />
              </template>
            </Column>

            <Column field="completeness_score" class="min-w-40">
              <template #header>
                <div
                  class="flex cursor-pointer items-center justify-center gap-1"
                  @click="onSort({ field: 'completeness_score' })"
                >
                  <span>Completeness Score</span>
                  <component :is="getSortIcon('completeness_score')" class="size-4" />
                </div>
              </template>
              <template #body="{ data }">
                <div class="flex items-center gap-2">
                  <div class="flex-1">
                    <ProgressBar
                      :value="data.completeness_score"
                      :showValue="false"
                      class="!h-1.5"
                      :class="`progress-${getProgressBarColor(data.quality_category)}`"
                    />
                  </div>
                  <span class="whitespace-nowrap text-sm font-semibold">
                    {{ data.completeness_score }}
                  </span>
                </div>
              </template>
            </Column>
          </DataTable>
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

  <!-- Ticket Detail Modal -->
  <TicketDetailModal v-model:visible="modalVisible" :ticket-id="selectedTicketId" />
</template>
