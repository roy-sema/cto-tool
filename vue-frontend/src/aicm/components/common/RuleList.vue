<script setup lang="ts">
import RuleTooltip from "@/aicm/components/common/RuleTooltip.vue";
import type { Rule } from "@/aicm/helpers/api.d";

const props = defineProps<{
  rules: [Rule, string][];
}>();
</script>

<template>
  <ul class="ml-1">
    <li
      v-for="[rule, color] in props.rules"
      :key="rule.public_id"
      class="rule justify-left mb-3 flex gap-2 text-sm font-light"
    >
      <div :class="`h-5 w-5 risk-3d-${color} shrink-0 rounded-full shadow-2xl`"></div>
      <RuleTooltip :rule />
    </li>
  </ul>
</template>
