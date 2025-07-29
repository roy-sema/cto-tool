<!-- https://tw-elements.com/docs/standard/components/spinners/ -->
<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    size?: number;
    text?: string;
  }>(),
  {
    size: 8,
    text: "Loading...",
  },
);

const borderClass = computed(() => {
  const width = Math.floor(props.size / 2);
  return width > 1 ? `border-${width}` : "border";
});
</script>

<template>
  <div
    :class="`inline-block size-${props.size} animate-spin rounded-full ${borderClass} border-solid border-current border-e-transparent align-[-0.125em] text-surface motion-reduce:animate-[spin_1.5s_linear_infinite] dark:text-white`"
    role="status"
  >
    <span
      v-if="props.text"
      class="!absolute !-m-px !h-px !w-px !overflow-hidden !whitespace-nowrap !border-0 !p-0 ![clip:rect(0,0,0,0)]"
    >
      {{ props.text }}
    </span>
  </div>
</template>
