<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import FlightDeckCard from "@/compass/components/FlightDeckCard.vue";
import { getDashboardData } from "@/compass/helpers/api";
import { avatarTitle } from "@/compass/helpers/utils";
import { DocumentIcon, ExclamationTriangleIcon, InformationCircleIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { computed, onMounted, ref } from "vue";

// TODO: move to API
interface Insight {
  status: string;
  text: string;
}

interface Member {
  name: string;
  pic: string;
}

const maxAvatars = 4;

const loading = ref(true);
const insights = ref<Insight[]>([]);
const subscribedMembers = ref<Member[]>([]);
const summary = ref("");
const updatedAt = ref();

// TODO: get from backend
const flightDeckCards = [
  {
    title: "Initiative Roadmap",
    progress: {
      percentage: 45,
      delta: -8,
      detail: "2 of 4 on track",
      status: "danger",
    },
    details: [
      { status: "danger", text: "OSS Fixes", detail: "20% complete" },
      { status: "ok", text: "CheckMarks Fix", detail: "70% complete" },
      { status: "ok", text: "GenAI/GBOM Automation", detail: "60% complete" },
      { status: "warning", text: "GenAI Report Pages", detail: "60% complete" },
    ],
    integrations: {
      github: { status: true, display_name: "GitHub" },
      jira: { status: true, display_name: "Jira" },
    } as IntegrationStatusMap,
    route: "roadmap",
  },
  {
    title: "Policy Compliance",
    progress: {
      percentage: 82,
      delta: -5,
      detail: "23 rules met",
      status: "warning",
    },
    details: [
      { status: "warning", text: "GenAI Usage > 30%", detail: "35% repos" },
      { status: "warning", text: "Code Quality Gates", detail: "15% fails" },
      { status: "warning", text: "Test Coverage < 80%", detail: "12% repos" },
    ],
    integrations: {
      jira: { status: true, display_name: "Jira" },
      github: { status: true, display_name: "GitHub" },
      aws: { status: true, display_name: "AWS" },
    } as IntegrationStatusMap,
    route: "compliance",
  },
  {
    title: "Team Health",
    progress: {
      percentage: 78,
      delta: 0,
      detail: "9 goals met",
      status: "ok",
    },
    details: [
      { status: "danger", text: "Team Retention", detail: "76%" },
      { status: "danger", text: "Cycle Time", detail: "9 days" },
      { status: "danger", text: "On-call Incidents", detail: "+ 45%" },
    ],
    integrations: {
      jira: { status: true, display_name: "Jira" },
      workplace: { status: true, display_name: "Workplace" },
      jenkins: { status: true, display_name: "Jenkins" },
    } as IntegrationStatusMap,
    route: "team",
  },
  {
    title: "Budget Performance",
    progress: {
      percentage: 88,
      delta: 4,
      detail: "$4400 under budget",
      status: "ok",
    },
    details: [
      { status: "danger", text: "Cloud Costs", detail: "120k under" },
      { status: "ok", text: "Contractor Spend", detail: "85k under" },
      { status: "ok", text: "Tool Licenses", detail: "45k under" },
    ],
    integrations: {
      aws: { status: true, display_name: "AWS" },
      quickbooks: { status: true, display_name: "Quickbooks" },
    } as IntegrationStatusMap,
    route: "budget",
  },
];

const insightsWithIcon = computed(() => {
  return insights.value.map((insight) => {
    const { icon, color } = getStatusIcon(insight.status);
    return { ...insight, icon, color };
  });
});

const loadData = async () => {
  try {
    loading.value = true;

    const response = await getDashboardData();
    updatedAt.value = response.updated_at;

    // TODO: get from backend
    summary.value =
      "Overall declining trends continue: Initiatives (-8%), Compliance (-5%), Team Health (-7%), and Budget performance (-4%). Budget overruns in cloud and contractor costs partially offset by license savings. Immediate action needed to address Payment Integration delays and rising operational costs.";
    insights.value = [
      {
        status: "info",
        text: "Rising contractor costs linked to Payment Integration delays - consider permanent hiring",
      },
      {
        status: "warning",
        text: "Current trajectory suggests Q4 budget at risk - immediate cost controls recommended",
      },
      {
        status: "danger",
        text: "Cloud cost overruns correlate with increasing on-call incidents - infrastructure optimization needed",
      },
    ];
    subscribedMembers.value = [
      { name: "John Doe", pic: "" },
      { name: "Matt", pic: "" },
      { name: "Brendan", pic: "" },
      { name: "Roy", pic: "" },
      { name: "Jafar", pic: "" },
      { name: "Marc", pic: "" },
    ];
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const getStatusIcon = (status: string) =>
  ({
    warning: { icon: ExclamationTriangleIcon, color: "yellow-400" },
    danger: { icon: ExclamationTriangleIcon, color: "red-600" },
  })[status] || { icon: InformationCircleIcon, color: "cyan-600" };

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader title="Dashboard" :updatedAt="updatedAt" :comingSoon="true" :loading="loading">
    <template #right>
      <div class="flex items-center">
        <Button label="Write Executive Summary" severity="contrast">
          <template #icon>
            <DocumentIcon class="size-5" />
          </template>
        </Button>
      </div>
    </template>
  </PageHeader>

  <div class="mt-3 grid gap-x-2 gap-y-5 px-4 sm:grid-cols-2 lg:px-6">
    <div class="flex items-start gap-2 rounded-md border border-cyan-600 bg-cyan-50 px-4 py-3 dark:bg-cyan-950">
      <InformationCircleIcon class="mt-0.5 size-4 shrink-0 text-cyan-600" />
      <div class="text-sm text-cyan-800 dark:text-cyan-600">
        This dashboard shows the current daily snapshot of your engineering department's performance across initiatives,
        compliance, team health, and budget metrics. Data is updated every 24 hours.
      </div>
    </div>

    <div class="flex items-start sm:justify-end">
      <div class="flex flex-col gap-2">
        <div class="pl-1 font-semibold">Subscribed</div>
        <ProgressSpinner v-if="loading" class="!size-8" />
        <AvatarGroup v-else>
          <Avatar
            v-for="member in subscribedMembers.slice(0, maxAvatars)"
            :key="member.name"
            :label="avatarTitle(member.name)"
            :src="member.pic"
            shape="circle"
          />
          <Avatar
            v-if="subscribedMembers.length > maxAvatars"
            :label="`+${subscribedMembers.length - maxAvatars}`"
            shape="circle"
          />
        </AvatarGroup>
      </div>
    </div>
  </div>

  <div class="mt-3 grid gap-x-2 gap-y-3 px-4 sm:grid-cols-2 lg:px-6 xl:grid-cols-4">
    <FlightDeckCard v-for="card in flightDeckCards" :key="card.title" :card="card" :loading="loading" />
  </div>

  <div class="mt-3 grid gap-x-2 gap-y-5 px-4 pb-10 sm:grid-cols-2 lg:px-6">
    <Panel>
      <template #header>
        <div class="flex w-full justify-between">
          <h3 class="text-md font-semibold">Daily Summary</h3>
          <Tag severity="info" value="AI" class="!text-xs !font-normal" />
        </div>
      </template>

      <div v-if="loading" class="flex items-center justify-center">
        <ProgressSpinner />
      </div>
      <div v-else>
        <p class="break-words text-sm font-normal text-muted-color">{{ summary || "There is no summary." }}</p>
      </div>
    </Panel>

    <Panel>
      <template #header>
        <div class="flex w-full justify-between">
          <h3 class="text-md font-semibold">Key Insights & Recommendations</h3>
          <Tag severity="info" value="AI" class="!text-xs !font-normal" />
        </div>
      </template>

      <div v-if="loading" class="flex items-center justify-center">
        <ProgressSpinner />
      </div>
      <div v-else-if="!insights || insights.length === 0">
        <p class="text-sm">There are no insights.</p>
      </div>
      <div v-else>
        <div v-for="(insight, index) in insightsWithIcon" :key="index">
          <div class="flex items-start gap-2">
            <component :is="insight.icon" class="mt-0.5 size-4 shrink-0" :class="`text-${insight.color}`" />
            <p class="break-words text-sm font-normal text-muted-color">{{ insight.text }}</p>
          </div>
          <Divider v-if="index !== insights.length - 1" />
        </div>
      </div>
    </Panel>
  </div>
</template>

<style scoped>
:deep(.p-avatar-group .p-avatar) {
  @apply border-slate-50 dark:border-slate-800;
}
</style>
