<script setup lang="ts">
import PillTag from "@/aicm/components/common/PillTag.vue";
import type { Rule } from "@/aicm/helpers/api.d";
import { Popover, initTWE } from "tw-elements";
import { onMounted } from "vue";

const props = defineProps<{
  rule: Rule;
  placement?: string;
  is_pill?: boolean;
  color?: string;
}>();

// This has no reactivity, since rule prop is not expected to change.
// Change to computed if rule prop is expected to change.
const content = `
  <div class='mb-1 text-xs'>${props.rule.rule_str}</div>
  <ul class='ml-5 list-disc'>
    ${props.rule.conditions.map((c) => `<li class='text-xs'>${c.condition_str}</li>`).join("")}
  </ul>
`;

onMounted(() => initTWE({ Popover }, { allowReinits: true }));
</script>

<template>
  <div
    class="font-semibold"
    :class="{ 'cursor-help': !props.is_pill }"
    data-twe-toggle="popover"
    :data-twe-title="props.rule.name"
    :data-twe-placement="props.placement"
    :data-twe-content="content"
    data-twe-html="true"
    data-twe-trigger="hover focus"
  >
    <PillTag v-if="props.is_pill" :text="props.rule.name" :color="`risk-bg-${props.color} risk-text-${props.color}`" />
    <template v-else>
      {{ props.rule.name }}
    </template>
  </div>
</template>

<!-- This is not scoped! -->
<style>
/* HACK: kinda .. to make popovers darker */
div[class*="te-popover-"] {
  @apply text-xs dark:bg-neutral-700;
}
</style>
