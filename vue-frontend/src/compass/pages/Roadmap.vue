<script setup lang="ts">
import { round } from "@/aicm/helpers/utils";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import { getProductRoadmapData, getProductRoadmapFilters } from "@/compass/helpers/api";
import type { Initiative, OrganizationRepositoryGroup, ProductRoadmapResponse } from "@/compass/helpers/api.d";
import { router } from "@/router";
import { ArrowRightIcon, CheckCircleIcon, InformationCircleIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import Dialog from "primevue/dialog";
import { computed, onMounted, ref } from "vue";

const loading = ref(true);
const updatedAt = ref();
const selectedFilter = ref({ repoGroup: "" });
const repoGroupsFilters = ref<OrganizationRepositoryGroup[]>([]);
const roadmapData = ref<ProductRoadmapResponse>({ roadmap_ready: false } as ProductRoadmapResponse);

const dateRange = ref<[Date, Date]>();
const searchText = ref("");
const activeInitiatives = ref<number[]>([]);

const isOnboarding = computed(() => (router.currentRoute.value.name as string).startsWith("onboarding-"));
const hasJira = computed(() => roadmapData.value?.integrations?.jira?.status === true || false);

const loadData = async () => {
  try {
    loading.value = true;
    const filtersResponse = await getProductRoadmapFilters();
    repoGroupsFilters.value = filtersResponse.repository_groups;

    if (filtersResponse.repository_groups.length == 0) {
      return;
    }
    selectedFilter.value.repoGroup = filtersResponse.repository_groups[0].public_id;
    await loadRoadmapData();
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const loadRoadmapData = async () => {
  try {
    loading.value = true;
    roadmapData.value = await getProductRoadmapData(selectedFilter.value.repoGroup);
    if (!roadmapData.value.roadmap_ready) {
      updatedAt.value = null;
      dateRange.value = undefined;
      return;
    }

    updatedAt.value = roadmapData.value.updated_at;
    const [fromDate, toDate] = roadmapData.value.date_range;
    dateRange.value = [new Date(fromDate * 1000), new Date(toDate * 1000)];
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const initiativesFiltered = computed(() => {
  if (searchText.value === "") return roadmapData.value?.initiatives;
  return roadmapData.value?.initiatives?.filter((initiative) => {
    return initiative.name.toLocaleLowerCase().includes(searchText.value.trim().toLocaleLowerCase());
  });
});

const insights = computed(() => roadmapData.value?.initiatives?.map((initiative) => initiative.justification));
const hasInsights = computed(() => (insights.value && insights.value.length > 0) || roadmapData.value?.summary);
const epicsCount = computed(() =>
  roadmapData.value?.initiatives?.reduce((acc, initiative) => acc + initiative.epics.length, 0),
);

const showDialog = ref(false);
const selectedDeliveryEstimate = ref(); // will hold the clicked initiative delivery estimate

const humanReadableDate = (date: string | number) => {
  if (!date) return null;
  const parsed_date = new Date(date);
  if (isNaN(parsed_date.getTime())) return null;

  return parsed_date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
};

const getEstimatedDates = (initiative: Initiative) => {
  if (!initiative.start_date || !initiative.estimated_end_date) return null;
  return `${humanReadableDate(initiative.start_date)} to ${humanReadableDate(initiative.estimated_end_date)}`;
};

const headers = [
  {
    label: "Initiatives & Epics",
    tooltipText: `<p>An "Initiative” is a work group consisting of one or more "Epics”.</p>Initiatives are generally (but not always!) suitable for updates to less technical audiences, while Epics are more detailed breakouts for Engineering.`,
  },
  {
    label: "% of development",
    tooltipText: "<p>Percentage of total development work in this period spent on this Work Group<p>",
  },
  {
    label: "Estimated % of work completed",
    tooltipText: "<p>Percentage of total development to be completed on this Work Group that is already complete<p>",
  },
  {
    label: "Estimated delivery date BETA",
    tooltipText:
      "<p>This is an AI-produced estimated date range for when work group items will be delivered. Currently in early beta, treat with skepticism<p>",
  },
];

const insightOverviewTooltipText =
  "<p>Recap of the overall development activity by Work Group (Initiatives and Epics)<p>";

const insightDetailTooltipText =
  "<p>Specific examples of the overall development activity by Work Group (Initiatives and Epics)<p>";

const reconciliationTooltipText = `<p>Work groups in this section are generated when there is
  (a) high development activity but few/no tickets (indicating potentially untracked work) or
  (b) many tickets but minimal development activity (indicating potential planning efforts).<p>`;

const hasEpics = (initiative: Initiative) => initiative.epics?.length > 0;
const hasDeliveryEstimate = (initiative: Initiative) => initiative.delivery_estimate?.length > 0;

const openDeliveryEstimateDialog = (initiative: Initiative) => {
  selectedDeliveryEstimate.value = initiative.delivery_estimate;
  showDialog.value = true;
};

const expandAll = () => {
  activeInitiatives.value = Array.from({ length: roadmapData.value?.initiatives?.length || 0 }, (_, index) => index);
};
const collapseAll = () => {
  activeInitiatives.value = [];
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader
    v-if="!isOnboarding"
    title="Product Roadmap"
    :updatedAt="updatedAt"
    :integrations="roadmapData.integrations"
    :loading="loading"
    :dateRange="dateRange"
  />

  <Message
    v-if="!loading && !isOnboarding && !hasJira"
    severity="warn"
    class="mb-2 !rounded-none px-5"
    :pt="{ text: 'flex justify-between flex-row w-full items-center' }"
  >
    <div class="text-sm">Connect Jira to see each Initiative's estimated work completion and delivery dates.</div>
    <Button variant="link" as="a" href="/settings/connections/">Connect to Jira</Button>
  </Message>

  <Message
    v-if="!loading && isOnboarding"
    severity="warn"
    class="mb-2 !rounded-none px-5"
    :pt="{ text: 'flex justify-between flex-row w-full items-center' }"
  >
    <div class="w-full flex-row text-center text-sm">
      <div>
        This is an automatic summary of Development Activity by Initiative for the last two weeks, by only reviewing
        Development Activity.
      </div>
      <div>
        This will likely take minimum 15 minutes, and could run overnight. Feel free to come back and see this page
        later in the Product Roadmap Radar.
      </div>
    </div>
  </Message>
  <div class="px-4 pt-4 lg:px-6 lg:pt-6">
    <Select
      v-model="selectedFilter.repoGroup"
      :options="repoGroupsFilters"
      optionLabel="name"
      optionValue="public_id"
      placeholder="Select Product"
      class="w-full md:w-56"
      filter
      @change="loadRoadmapData"
    />
  </div>

  <div class="flex flex-col justify-between gap-5 px-4 py-5 lg:px-6 xl:flex-row">
    <div class="flex shrink-0 flex-col gap-5 rounded-md xl:w-2/3">
      <Panel>
        <template #header>
          <div class="flex w-full items-center justify-between">
            <template v-if="!loading && roadmapData.initiatives?.length">
              <div class="text-sm text-muted-color">
                Last {{ roadmapData.default_time_window_days }} days. Showing
                {{ roadmapData.initiatives?.length }} active
                {{ roadmapData.initiatives?.length === 1 ? "Initiative" : "Initiatives" }} and {{ epicsCount }} active
                {{ epicsCount === 1 ? "Epic" : "Epics" }}
              </div>
              <div>
                <Button variant="link" size="small" class="!py-0" @click="expandAll">Expand All</Button>
                <Button variant="link" size="small" class="!py-0" @click="collapseAll">Collapse All</Button>
              </div>
            </template>
          </div>
        </template>
        <!-- TODO not liking the w-[80vw] here, but it's a quick fix for now -->
        <div class="flex max-w-[80vw] flex-col gap-5 overflow-x-auto pb-2 sm:max-w-full">
          <div v-if="loading" class="flex items-center justify-center">
            <ProgressSpinner class="!size-10" />
          </div>
          <div
            v-else-if="!roadmapData.initiatives || roadmapData.initiatives?.length == 0"
            class="flex items-center justify-center"
          >
            <p class="text-sm text-muted-color">There are no Initiatives.</p>
          </div>
          <template v-else>
            <div
              v-if="!roadmapData.initiatives || initiativesFiltered?.length == 0"
              class="flex items-center justify-center"
            >
              <p class="text-sm">There are no Initiatives that match your query</p>
            </div>

            <div class="flex flex-col gap-4">
              <div class="flex gap-4">
                <div class="mr-2 w-4"><!-- mimic icon --></div>
                <div v-for="(header, index) in headers" :key="index" class="flex-1">
                  <div class="flex items-start gap-1" :class="{ 'ml-10': index === headers.length - 1 }">
                    <div>{{ header.label }}</div>
                    <InformationCircleIcon
                      v-tooltip.top="{
                        value: header.tooltipText,
                        escape: false,
                        autoHide: false,
                        pt: { text: 'text-xs' },
                      }"
                      class="mt-1 size-4 shrink-0 cursor-pointer text-blue"
                    />
                  </div>
                </div>
              </div>

              <hr class="w-screen sm:w-full" />

              <Accordion v-model:value="activeInitiatives" class="w-screen sm:w-full" multiple>
                <AccordionPanel
                  v-for="(initiative, index) in initiativesFiltered"
                  :key="index"
                  :value="index"
                  :pt="{ root: 'last:!border-none ' }"
                  :class="{ 'inactive-accordion': !hasEpics(initiative) }"
                >
                  <AccordionHeader :pt="{ root: '!px-0 !flex !gap-4 !text-sm', toggleIcon: 'order-first mr-2' }">
                    <template v-if="!hasEpics(initiative)" #toggleicon>
                      <div class="order-first mr-2 w-4"><!-- mimic icon --></div>
                    </template>
                    <div class="flex-1">{{ initiative.name }}</div>
                    <div class="flex flex-1 flex-col gap-1">
                      <div class="text-xs">{{ round(initiative.percentage) }}%</div>
                      <ProgressBar :value="initiative.percentage" :show-value="false" class="!h-1.5" />
                    </div>
                    <div class="flex flex-1 flex-col gap-1">
                      <div class="text-xs">{{ round(initiative.percentage_tickets_done) }}% completed</div>
                      <ProgressBar :value="initiative.percentage_tickets_done" :show-value="false" class="!h-1.5" />
                    </div>
                    <div class="flex-1 self-center" @click.stop="openDeliveryEstimateDialog(initiative)">
                      <div class="flex items-center justify-end gap-1" title="Delivery estimate">
                        {{ getEstimatedDates(initiative) || "N/A" }}
                        <InformationCircleIcon
                          title="Delivery estimate"
                          class="size-4 shrink-0 cursor-pointer text-blue"
                          :class="{ invisible: !hasDeliveryEstimate(initiative) }"
                          @click.stop="openDeliveryEstimateDialog(initiative)"
                        />
                      </div>
                    </div>
                  </AccordionHeader>
                  <AccordionContent :pt="{ content: '!p-0 ' }">
                    <div
                      v-for="(epic, index) in initiative.epics"
                      :key="index"
                      class="my-2 flex gap-4 text-xs text-muted-color first:mt-0"
                    >
                      <div class="flex-1">{{ epic.name }}</div>
                      <div class="flex flex-1 flex-col gap-1">
                        <div class="text-xs text-muted-color">{{ round(epic.percentage) }}%</div>
                        <ProgressBar :value="epic.percentage" :show-value="false" class="progress-cyan !h-1.5" />
                      </div>
                      <div class="flex flex-1 flex-col gap-1"></div>

                      <div class="flex-1 self-center text-right text-sm"></div>
                      <div class="order-first mr-2 w-4"><!-- mimic icon --></div>
                    </div>
                  </AccordionContent>
                </AccordionPanel>
              </Accordion>
              <Dialog v-model:visible="showDialog" modal header="Delivery Estimate">
                <div class="overflow-y-auto whitespace-pre-line p-3">
                  {{ selectedDeliveryEstimate }}
                </div>
              </Dialog>
            </div>
          </template>
        </div>
      </Panel>

      <Panel>
        <template #header>
          <div class="flex w-full flex-col gap-4">
            <div class="flex w-full justify-between gap-2">
              <div class="flex items-center gap-1">
                <div class="text-xl">Roadmap work to be reconciled</div>
                <InformationCircleIcon
                  v-tooltip.top="{
                    value: reconciliationTooltipText,
                    escape: false,
                    autoHide: false,
                    pt: { text: 'text-xs' },
                  }"
                  class="size-4 shrink-0 cursor-pointer text-blue"
                />
              </div>
              <div
                v-if="
                  !loading && roadmapData.reconcilable_initiatives && roadmapData.reconcilable_initiatives?.length != 0
                "
                class="text-muted-colo flex gap-0.5 text-sm"
              >
                <CheckCircleIcon class="mt-0.5 size-4 min-w-4 text-amber-400" />
                {{ roadmapData.reconcilable_initiatives?.length }}
                {{ roadmapData.reconcilable_initiatives?.length === 1 ? "Initiative" : "Initiatives" }} Affected
              </div>
            </div>
            <div
              v-if="
                !loading && roadmapData.reconcilable_initiatives && roadmapData.reconcilable_initiatives?.length != 0
              "
              class="text-sm text-muted-color"
            >
              Development activity without clear mapping to Product Management tool activity, and vice versa
            </div>
          </div>
        </template>
        <div class="flex max-w-[80vw] flex-col gap-5 overflow-x-auto pb-2 sm:max-w-full">
          <div v-if="loading" class="flex items-center justify-center">
            <ProgressSpinner class="!size-10" />
          </div>
          <div
            v-else-if="!roadmapData.reconcilable_initiatives || roadmapData.reconcilable_initiatives?.length == 0"
            class="flex items-center justify-center"
          >
            <p class="text-sm text-muted-color">There are no Initiatives to be reconciled.</p>
          </div>
          <template v-else>
            <!-- TODO mobile width support-->
            <div class="flex flex-col">
              <div class="grid gap-4">
                <div class="contents">
                  <div>Initiatives</div>
                  <div>Development Activity</div>
                  <div>Product Management Activity</div>
                </div>

                <hr class="col-span-3" />

                <template v-for="initiative in roadmapData.reconcilable_initiatives" :key="initiative.name">
                  <div class="contents text-sm">
                    <div>{{ initiative.name }}</div>
                    <div>{{ initiative.git_activity }}</div>
                    <div>{{ initiative.jira_activity }}</div>
                  </div>
                </template>
              </div>
            </div>
          </template>
        </div>
      </Panel>

      <div v-if="isOnboarding" class="mt-5 flex justify-center pb-20">
        <Button label="Next" :disabled="loading" @click="router.push({ name: 'onboarding-insights-notifications' })">
          <template #icon>
            <div class="order-1">
              <ArrowRightIcon class="size-4" />
            </div>
          </template>
        </Button>
      </div>
    </div>
    <div class="grow">
      <Panel>
        <template #header>
          <div class="flex w-full justify-between">
            <h2 class="text-xl">Insights</h2>
            <Tag severity="info" value="AI" class="!text-xs !font-normal" />
          </div>
        </template>
        <div v-if="loading" class="flex items-center justify-center">
          <ProgressSpinner class="!size-10" />
        </div>

        <p v-else-if="!hasInsights" class="text-sm text-muted-color">There are no insights.</p>
        <div v-else class="flex grow flex-col gap-2">
          <template v-if="hasJira">
            <Panel class="no-header-panel no-content-padding-panel !border-none">
              <div>
                <div class="flex items-center gap-1">
                  <h3 class="my-2 text-sm font-semibold">Summary Insights - Overview</h3>
                  <InformationCircleIcon
                    v-tooltip.top="{
                      value: insightOverviewTooltipText,
                      escape: false,
                      autoHide: false,
                      pt: { text: 'text-xs' },
                    }"
                    class="size-4 shrink-0 cursor-pointer text-blue"
                  />
                </div>
                <p class="break-words text-sm font-normal text-muted-color">
                  {{ roadmapData.summary || "There is no summary." }}
                </p>
              </div>
            </Panel>

            <hr class="my-3" />
          </template>

          <Panel class="no-header-panel no-content-padding-panel !border-none">
            <div class="flex items-center gap-1">
              <h3 class="my-2 text-sm font-semibold">Summary Insights - Detail</h3>
              <InformationCircleIcon
                v-tooltip.top="{
                  value: insightDetailTooltipText,
                  escape: false,
                  autoHide: false,
                  pt: { text: 'text-xs' },
                }"
                class="size-4 shrink-0 cursor-pointer text-blue"
              />
            </div>
            <div>
              <div v-for="(insight, index) in insights" :key="index">
                <div class="flex items-start gap-2">
                  <CheckCircleIcon class="mt-0.5 size-4 min-w-4 text-green-700" />
                  <p class="break-words text-sm font-normal text-muted-color">{{ insight }}</p>
                </div>
                <Divider v-if="insights && index !== insights.length - 1" />
              </div>
            </div>
          </Panel>
        </div>
      </Panel>
    </div>
  </div>
</template>
