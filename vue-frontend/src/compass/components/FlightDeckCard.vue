<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import Integrations from "@/compass/components/Integrations.vue";
import {
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  ExclamationCircleIcon,
  XCircleIcon,
} from "@heroicons/vue/24/outline";
import { computed } from "vue";

// TODO: move to API
interface FlightDeckCard {
  title: string;
  progress: {
    percentage: number;
    delta: number;
    detail: string;
    status: string;
  };
  details: {
    status: string;
    text: string;
    detail: string;
  }[];
  integrations: IntegrationStatusMap;
  route: string;
}

const props = defineProps<{
  card: FlightDeckCard;
  loading?: boolean;
}>();

const deltaText = computed(() => {
  const delta = props.card.progress.delta;
  const text = `${delta >= 0 ? "on track" : "declined by"}`;
  const percentage = `${delta >= 0 ? "+" : ""}${delta.toFixed(0)}%`;
  return `${text} ${percentage}`;
});

const detailsWithIcon = computed(() => {
  return props.card.details.map((detail) => {
    const { icon, color } = getStatusIcon(detail.status);
    return { ...detail, icon, color };
  });
});

const progressColor = computed(
  () =>
    ({
      warning: "orange-700",
      danger: "red-600",
    })[props.card.progress.status] || "green-700",
);

const progressSeverity = computed(
  () =>
    ({
      ok: "success",
      warning: "warn",
      danger: "danger",
    })[props.card.progress.status],
);

const getStatusIcon = (status: string) =>
  ({
    warning: { icon: ExclamationCircleIcon, color: "orange-600" },
    danger: { icon: XCircleIcon, color: "red-600" },
  })[status] || { icon: CheckCircleIcon, color: "green-700" };
</script>

<template>
  <Panel>
    <template #header>
      <h3 class="text-md -mb-2 font-semibold">{{ card.title }}</h3>
    </template>

    <div v-if="loading" class="flex h-48 items-center justify-center">
      <ProgressSpinner />
    </div>

    <template v-else>
      <Tag
        :severity="progressSeverity"
        :value="deltaText"
        class="border !py-0.5 !font-normal"
        :class="`border-${progressColor}`"
      >
        <template #icon>
          <div v-if="!props.card.progress.delta" class="flex">
            <ArrowLeftIcon class="size-3" />
            <ArrowRightIcon class="size-3" />
          </div>
          <ArrowUpIcon v-else-if="props.card.progress.delta > 0" class="size-4" />
          <ArrowDownIcon v-else class="size-4" />
        </template>
      </Tag>

      <div class="mt-4 flex items-center gap-3">
        <div class="text-2xl font-semibold">{{ card.progress.percentage }}%</div>
        <div>
          <div class="whitespace-nowrap rounded-md bg-slate-100 px-2 py-1 text-sm font-normal dark:bg-slate-800">
            {{ card.progress.detail }}
          </div>
        </div>
      </div>

      <div class="mt-4 flex h-20 flex-col gap-1">
        <div v-for="(detail, index) in detailsWithIcon" :key="index" class="flex items-center justify-between gap-1">
          <div class="flex items-center gap-1" :class="`text-${detail.color}`">
            <component :is="detail.icon" class="size-3 shrink-0" />
            <p class="break-words text-xs font-normal">{{ detail.text }}</p>
          </div>
          <div class="whitespace-nowrap text-xs text-muted-color">{{ detail.detail }}</div>
        </div>
      </div>

      <div class="mt-3">
        <div class="text-xs font-semibold text-muted-color">Integrations</div>
        <Integrations :integrations="card.integrations" class="mt-1" />
      </div>
    </template>

    <template #footer>
      <router-link
        :to="{ name: card.route }"
        class="absolute inset-x-0 flex h-full items-center justify-between gap-2 rounded-b-md border-t px-5 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-700"
      >
        <span class="text-sm">See more</span>
        <ChevronRightIcon class="size-3.5" />
      </router-link>
    </template>
  </Panel>
</template>

<style scoped>
:deep(.p-panel-footer) {
  @apply relative h-12;
}

:deep(.integration) {
  @apply bg-slate-100 p-1 text-muted-color dark:bg-slate-800;
}
</style>
