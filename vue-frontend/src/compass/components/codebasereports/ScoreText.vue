<script setup lang="ts">
import type { Score } from "@/compass/helpers/api.d";

defineProps<{
  score: Score;
  scoreLastWeek: Score;
}>();
</script>

<template>
  <p>
    Codebase Health Score
    <span v-if="score.score === scoreLastWeek.score"> remained </span>
    <span v-else>
      <span v-if="score.score > scoreLastWeek.score">increased</span>
      <span v-else>decreased</span> from
      <span :class="`font-semibold text-level-${scoreLastWeek.color}`">{{ scoreLastWeek.score }}</span> to
    </span>
    <span :class="`font-semibold text-level-${score.color}`">{{ score.score }}</span> over the last week.
  </p>

  <p class="mt-3">
    The codebase is in the <span :class="`font-semibold text-level-${score.color}`">{{ score.phase }}</span> phase.
  </p>
</template>
