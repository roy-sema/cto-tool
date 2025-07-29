<script setup lang="ts">
import TargetIcon from "@/compass/assets/icons/target.svg?component";
import type { TeamHealthMetric } from "@/compass/helpers/api.d";
import { PlayIcon } from "@heroicons/vue/24/outline";
import { computed } from "vue";
import MultiValueProgressBar from "./common/MultiValueProgressBar.vue";

const props = defineProps<{
  metric: TeamHealthMetric;
}>();

const severity = computed(() => {
  const severityMap = {
    red: "danger",
    yellow: "warn",
    green: "success",
  };
  return severityMap?.[props.metric.color] || severityMap.green;
});

const percentageCurrent = computed(() => {
  return (props.metric.current / props.metric.max) * 100;
});

const percentageGoal = computed(() => {
  return (props.metric.goal / props.metric.max) * 100;
});

const currentValue = computed(() => {
  return `${props.metric.current}${props.metric.postfix}`;
});

const goalValue = computed(() => {
  return `${props.metric.goal}${props.metric.postfix}`;
});
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
              <div class="ml-1 whitespace-nowrap">Current: {{ currentValue }}</div>
            </div>
            <div>•</div>
            <div class="flex items-center">
              <TargetIcon class="size-3.5" />
              <div class="ml-1 whitespace-nowrap">Goal: {{ goalValue }}</div>
            </div>
          </div>
        </div>
        <div>
          <Tag :severity="severity" :value="metric.status" class="!text-xs !font-normal" />
        </div>
      </div>

      <MultiValueProgressBar
        :value="percentageCurrent"
        :value-label="currentValue"
        :value-secondary="percentageGoal"
        :value-secondary-label="goalValue"
        :color="metric.color"
      />
    </div>
  </Panel>
</template>
