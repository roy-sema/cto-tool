<script setup lang="ts">
import { Popover, initTWE } from "tw-elements";
import { computed, onMounted } from "vue";

const props = defineProps<{
  title: string;
  content: string;
  numerator: number;
  denominator: number;
}>();

const percentage = computed(() => {
  if (props.denominator === 0) return 0;
  return (props.numerator / props.denominator) * 100;
});

onMounted(() => initTWE({ Popover }, { allowReinits: true }));
</script>

<template>
  <!-- TODO Title does not get updated, so was removed for now -->
  <div
    class="w-full text-xs font-light"
    data-twe-toggle="popover"
    data-twe-placement="top"
    data-twe-trigger="hover focus"
    :data-twe-content="content"
  >
    <div class="w-full overflow-clip rounded-full bg-neutral-200 dark:bg-slate-600">
      <div
        class="bg-blue p-0.5 text-center text-xs font-medium leading-none text-primary-100"
        :style="{ width: percentage + '%' }"
      >
        <span class="mx-1">{{ percentage.toFixed(2) }}%</span>
      </div>
    </div>
  </div>
</template>
