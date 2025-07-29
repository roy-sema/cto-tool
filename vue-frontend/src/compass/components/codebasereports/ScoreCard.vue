<script setup lang="ts">
import type { Score } from "@/compass/helpers/api.d";
import { ArrowTrendingDownIcon, ArrowTrendingUpIcon } from "@heroicons/vue/24/outline";

defineProps<{
  title: string;
  score: Score;
  max: number;
  difference?: number;
  noChart?: boolean;
}>();
</script>

<template>
  <div class="score-container">
    <h4 class="mb-3 font-semibold">{{ title }}</h4>
    <div
      class="flex h-60 w-full items-center justify-center rounded-xl border border-lightgrey shadow-lg dark:border-slate-600 md:h-80"
      :class="{ 'h-40 md:h-60': noChart }"
    >
      <div class="text-center">
        <div class="text-7xl font-extrabold xl:text-8xl" :class="`text-level-${score.color}`">{{ score.score }}</div>
        <div class="font-semibold text-gray-500">out of {{ max }}</div>
        <div v-if="difference" class="text-2xs font-semibold text-gray-500 md:text-xs">
          <component
            :is="difference > 0 ? ArrowTrendingUpIcon : ArrowTrendingDownIcon"
            class="inline size-4 opacity-50 dark:invert"
          />
          {{ difference > 0 ? `+${difference}` : difference }}
          from last week
        </div>
      </div>
    </div>
  </div>
</template>
