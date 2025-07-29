<script lang="ts" setup>
import { round } from "@/aicm/helpers/utils";
import { CpuChipIcon, UserCircleIcon } from "@heroicons/vue/24/outline";
import { computed } from "vue";

const props = defineProps<{
  aiOverall: number | string | undefined;
  aiPure: number | string | undefined;
  aiBlended: number | string | undefined;
  human: number | string | undefined;
  numLines?: number;
  size?: string;
  numFiles?: number;
}>();

const textSizeClass = computed(() => {
  return props.size === "sm" ? "text-sm md:text-base" : "text-base md:text-lg";
});

const iconSizeClass = computed(() => {
  return props.size === "sm" ? "w-4 md:w-5" : "w-5 md:w-6";
});

const computedAiOverall = computed(() => {
  return round(props.aiOverall);
});
const computedHuman = computed(() => {
  return round(props.human);
});
const computedAiPure = computed(() => {
  return round(props.aiPure);
});
const computedAiBlended = computed(() => {
  return round(props.aiBlended);
});
</script>

<template>
  <div class="flex gap-3 font-bold text-black dark:invert md:justify-between" :class="[textSizeClass]">
    <div class="flex items-center gap-1">
      <CpuChipIcon class="mr-1 inline group-hover:invert md:mr-1" :class="[iconSizeClass]" />
      <span v-if="!numFiles && !numLines">N/A</span>
      <span v-else>{{ computedAiOverall }}%</span>
    </div>
    <div class="flex items-center gap-1">
      <UserCircleIcon class="mr-1 inline group-hover:invert md:mr-1" :class="[iconSizeClass]" />
      <span v-if="!numFiles && !numLines">N/A</span>
      <span v-else>{{ computedHuman }}%</span>
    </div>
  </div>
  <div class="pl-1 pt-1 text-xs text-gray-500">
    <span v-if="!numFiles && !numLines"> Pure: N/A · Blended: N/A </span>
    <span v-else> Pure: {{ computedAiPure }}% · Blended: {{ computedAiBlended }}% </span>
  </div>
</template>
