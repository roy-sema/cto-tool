<script lang="ts" setup>
import { valueFormatted } from "@/aicm/helpers/utils";
import { QuestionMarkCircleIcon } from "@heroicons/vue/24/outline";
import { Popover, initTWE } from "tw-elements";
import { onMounted, ref } from "vue";
import ROICell from "./ROICell.vue";

const props = defineProps<{
  productivityAchievement: number;
  potentialProductivityCaptured: number;
  hoursSaved?: number;
  costSaved?: number;
  toolsCostSavedPercentage?: number;
  debugData?: Record<string, number>;
}>();

const showData = ref(false);
const hasTotalImpact = props.hoursSaved != null && props.costSaved != null;
const totalImpactSecondaryMetrics = (() => {
  if (!hasTotalImpact) return [];
  let metrics = [`$${props.costSaved.toLocaleString("en-US", { maximumFractionDigits: 0 })}`];
  if (props.toolsCostSavedPercentage != null) {
    metrics.push(`${props.toolsCostSavedPercentage.toLocaleString("en-US", { maximumFractionDigits: 0 })}% ROI`);
  }

  return metrics;
})();

onMounted(() => {
  const urlParams = new URLSearchParams(window.location.search);
  showData.value = urlParams.has("showData");

  initTWE({ Popover }, { allowReinits: true });
});
</script>

<template>
  <div class="flex max-h-96 flex-col-reverse gap-2 md:flex-row">
    <div class="flex w-full flex-col items-center gap-2 rounded-xl">
      <div class="flex text-lg font-bold">
        GenAI Coding ROI Dashboard
        <div
          class="mx-2 inline w-5 cursor-help pt-1 font-semibold"
          data-twe-placement="top"
          data-twe-toggle="popover"
          data-twe-content="Productivity Achievement and Potential Productivity Captured are based on GenAI ROI assumptions for the last
          2 weeks. The Date picker does not affect the results."
          data-twe-html="true"
          data-twe-trigger="hover focus"
        >
          <QuestionMarkCircleIcon class="w-5 font-semibold" />
        </div>
      </div>
      <div class="flex gap-2">
        <ROICell
          title="Productivity Achievement"
          :primaryMetric="valueFormatted(productivityAchievement)"
          :description="`GenAI has led to ${valueFormatted(productivityAchievement)}% increase in team productivity in the last 2 weeks.`"
        />
        <ROICell
          title="Potential Productivity Captured"
          :primaryMetric="valueFormatted(potentialProductivityCaptured)"
          :description="`${valueFormatted(potentialProductivityCaptured)}% of potential ROI of GenAI while coding has been captured in the last 2 weeks.`"
        />
        <ROICell
          v-if="hasTotalImpact"
          title="Total Impact"
          :primaryMetric="`${hoursSaved!.toLocaleString('en-US', { maximumFractionDigits: 0 })} Hours`"
          :secondaryMetrics="totalImpactSecondaryMetrics"
          description="Estimated annualized impact based on the last 2 weeks"
          :percentage="false"
        />
      </div>
      <div v-if="showData && debugData" class="overflow-y-scroll px-2 font-mono text-xs">
        DEBUG DATA:
        <div class="whitespace-pre-wrap">{{ JSON.stringify(debugData, null, 2) }}</div>
      </div>
    </div>
  </div>
</template>
