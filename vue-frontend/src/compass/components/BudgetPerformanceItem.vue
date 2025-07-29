<script setup lang="ts">
import TargetIcon from "@/compass/assets/icons/target.svg?component";
import type { BudgetPerformanceMetric } from "@/compass/helpers/api.d";
import { CheckCircleIcon, ExclamationCircleIcon, PlayIcon, XCircleIcon } from "@heroicons/vue/24/outline";
import { computed, ref } from "vue";

const props = defineProps<{
  metric: BudgetPerformanceMetric;
}>();

// changing this would also require to change the max-w- classes to make sure it doesn't overflow
const maxSubMetrics = 4;
const activeAccordion = ref();

const percentage = computed(() => {
  return (props.metric.current / props.metric.total_budget) * 100;
});

const severity = computed(() => {
  const severityMap = {
    red: "danger",
    yellow: "warn",
    green: "success",
  };
  return severityMap?.[props.metric.color] || severityMap.green;
});

const color = (color_name: "red" | "yellow" | "green"): string => {
  const colorMap = {
    red: "red-600",
    yellow: "amber-600",
    green: "green-700",
  };
  return colorMap?.[color_name] || colorMap.green;
};

const subMetricIcon = (color_name: "red" | "yellow" | "green"): any => {
  const iconMap = {
    red: XCircleIcon,
    yellow: ExclamationCircleIcon,
    green: CheckCircleIcon,
  };
  return iconMap?.[color_name] || iconMap.green;
};
</script>

<template>
  <Panel class="no-header-panel">
    <div class="flex flex-col gap-4">
      <div class="flex w-full justify-between">
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <h3 class="text-md font-semibold">{{ metric.name }}</h3>
          <div class="flex flex-wrap items-center gap-2 text-sm text-muted-color">
            <div class="flex items-center">
              <PlayIcon class="size-4" />
              <div class="ml-1 whitespace-nowrap">Current: ${{ metric.current.toLocaleString("en-US") }}</div>
            </div>
            <div>•</div>
            <div class="flex items-center">
              <TargetIcon class="size-3.5" />
              <div class="ml-1 whitespace-nowrap">Total Budget: ${{ metric.total_budget.toLocaleString("en-US") }}</div>
            </div>
          </div>
        </div>
        <div>
          <Tag :severity="severity" :value="`${percentage.toFixed(0)}%`" class="!text-xs !font-normal" />
        </div>
      </div>
      <ProgressBar :value="percentage" :show-value="false" class="!h-1.5" :class="`progress-${metric.color}`" />
      <Accordion v-if="metric.sub_metrics.length" v-model:value="activeAccordion">
        <AccordionPanel :value="metric.name">
          <AccordionHeader>
            <div class="mr-2 flex w-full items-center justify-between text-sm">
              <div class="min-w-max">See more</div>
              <div v-if="!activeAccordion" class="flex gap-4 text-xs">
                <!-- max-w- classes were chosen by manual testing to ensure the text doesn't overflow -->
                <div
                  v-for="subMetric in metric.sub_metrics.slice(0, maxSubMetrics)"
                  :key="subMetric.name"
                  class="hidden max-w-20 items-center gap-0.5 text-xs sm:flex md:max-w-32 xl:max-w-24 2xl:max-w-36"
                  :class="`text-${color(subMetric.color)}`"
                >
                  <component :is="subMetricIcon(subMetric.color)" class="size-4 min-w-4" />
                  <div class="truncate">{{ subMetric.name }}</div>
                </div>
                <div v-if="metric.sub_metrics.length > maxSubMetrics">
                  +{{ metric.sub_metrics.length - maxSubMetrics }}
                </div>
              </div>
            </div>
          </AccordionHeader>
          <AccordionContent>
            <div class="flex flex-col gap-2 text-xs">
              <div v-for="subMetric in metric.sub_metrics" :key="subMetric.name" class="flex justify-between">
                <div :class="`flex items-center gap-1 text-${color(subMetric.color)}`">
                  <component :is="subMetricIcon(subMetric.color)" class="size-4 min-w-4" />
                  <div>{{ subMetric.name }}</div>
                </div>
                <div class="text-muted-color">{{ subMetric.status }}</div>
              </div>
            </div>
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
    </div>
  </Panel>
</template>

<style scoped>
.p-accordionheader {
  @apply p-0;
}

:deep(.p-accordioncontent-content) {
  @apply px-2 pb-0 pt-2;
}

.p-accordionpanel {
  @apply border-none;
}
</style>
