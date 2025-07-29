<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import IntegrationsCard from "@/common/components/IntegrationsCard.vue";
import { toHumanReadableDate } from "@/compass/helpers/utils";
import { CalendarIcon, ClockIcon } from "@heroicons/vue/24/outline";
import { computed } from "vue";

const props = defineProps<{
  title: string;
  updatedAt?: number | null;
  comingSoon?: boolean;
  integrations?: IntegrationStatusMap;
  loading?: boolean;
  dateRange?: [Date, Date] | null;
  beta?: boolean;
}>();

const updatedAtHumanReadable = computed(() => toHumanReadableDate(props.updatedAt));

const formatDateRange = (date: Date) => {
  return date.toLocaleString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
};

const dateRangeHumanReadable = computed(() => {
  if (!props.dateRange) return "No data";
  const [fromDate, toDate] = props.dateRange;
  return `${formatDateRange(fromDate)} - ${formatDateRange(toDate)}`;
});
</script>

<template>
  <div class="border-b px-4 py-5 dark:border-slate-600 lg:px-6">
    <Message v-if="comingSoon" severity="warn" class="mb-5">
      <div class="font-bold">Coming Soon</div>
      <p class="text-sm">The data shown in this view is not real data and it's for demonstration purposes only.</p>
    </Message>
    <div class="flex w-full flex-col justify-between gap-2 md:flex-row">
      <div>
        <h1 class="mb-2 text-xl font-semibold">{{ title }}<sup v-if="beta"> BETA</sup></h1>
        <ProgressSpinner v-if="loading" class="!size-4" />
        <div v-else-if="updatedAt !== null" class="flex items-center gap-1 text-sm text-muted-color">
          <ClockIcon class="size-4 min-w-4" />
          <div>Last updated: {{ updatedAtHumanReadable }}</div>
        </div>

        <div v-if="dateRange" class="mt-2 flex items-center gap-1 text-sm text-muted-color">
          <CalendarIcon class="size-4 min-w-4" />
          <div>Date range: {{ dateRangeHumanReadable }}</div>
        </div>
      </div>
      <slot name="right">
        <IntegrationsCard
          v-if="integrations && Object.keys(integrations).length > 0"
          :integrations="integrations"
          class="w-full sm:w-80"
        />
      </slot>
    </div>
  </div>
</template>
