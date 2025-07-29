<script lang="ts" setup>
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    title: string;
    primaryMetric: string;
    secondaryMetrics?: string[];
    description?: string;
    percentage?: boolean;
  }>(),
  { percentage: true },
);

const textSize = computed(() => (props.secondaryMetrics?.length ? "sm:text-4xl" : "sm:text-5xl"));
</script>

<template>
  <div
    class="flex flex-1 flex-grow flex-col justify-between rounded-xl border border-lightgrey bg-white p-4 text-center shadow-md dark:border-slate-600 dark:bg-slate-700"
  >
    <div class="text-sm">{{ title }}</div>
    <div class="flex-col items-center text-xl font-bold text-blue" :class="textSize">
      <div class="my-2">{{ primaryMetric }}<template v-if="percentage">%</template></div>
      <div v-for="metric in secondaryMetrics" :key="metric" class="my-2">{{ metric }}</div>
    </div>
    <div v-if="description" class="text-xs text-gray-400 lg:mx-auto lg:w-2/3">{{ description }}</div>
  </div>
</template>
