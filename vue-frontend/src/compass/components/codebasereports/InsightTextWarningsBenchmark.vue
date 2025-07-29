<script setup lang="ts">
import type { Insight } from "@/compass/helpers/api.d";

defineProps<{
  insight: Insight;
  warningType: string;
}>();
</script>

<template>
  <div class="insight-container mb-5 rounded-xl border border-lightgrey p-4 text-sm shadow-md dark:border-slate-600">
    <p>
      This codebase is in the {{ insight.position }} {{ insight.percentile }} percent among all codebases for
      {{ warningType }} warnings.
    </p>
    <p class="mt-2">
      This puts the codebase in the
      <span :class="'text-level- font-bold' + insight.level">{{ insight.phase }}</span> phase. {{ insight.action }}
    </p>
    <p v-if="insight.remediation" class="mt-2">
      Remediating high priority {{ warningType }} warnings should take {{ insight.remediation.hours }} hours, which is
      equivalent to the total capacity of {{ insight.remediation.sprints }} sprints or ${{
        insight.remediation.dollars
      }}
      of developer time.
    </p>
  </div>
</template>
