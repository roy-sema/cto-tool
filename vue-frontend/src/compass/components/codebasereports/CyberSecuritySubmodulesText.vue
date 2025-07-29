<script setup lang="ts">
import { ArrowTrendingDownIcon, ArrowTrendingUpIcon } from "@heroicons/vue/24/outline";
import { computed } from "vue";

const props = defineProps<{
  submodules: { current: number; last_week: number };
}>();

const changeText = computed(() => {
  return props.submodules.current > props.submodules.last_week ? "increased" : "decreased";
});
</script>

<template>
  <div class="insight-container mb-5 rounded-xl border border-lightgrey p-4 text-sm shadow-md dark:border-slate-600">
    <component
      :is="submodules.current > submodules.last_week ? ArrowTrendingUpIcon : ArrowTrendingDownIcon"
      v-if="submodules.current !== submodules.last_week"
      class="inline size-4 dark:invert"
    />
    The number of sub-modules with cyber security risk
    <span v-if="submodules.current === submodules.last_week">remained</span>
    <span v-else>
      {{ changeText }} from <span class="font-semibold">{{ submodules.last_week }}</span> to
      <span class="font-semibold">{{ submodules.current }}</span>
    </span>
  </div>
</template>
