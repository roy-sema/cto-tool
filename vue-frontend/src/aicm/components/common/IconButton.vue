<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    icon: any;
    size?: number;
  }>(),
  {
    size: 5,
  },
);
</script>

<template>
  <button
    class="inline-block cursor-pointer rounded-full bg-lightgrey p-0.5 hover:bg-blue dark:bg-slate-600 dark:hover:bg-blue"
  >
    <component :is="props.icon" :class="`size-${props.size}`" />
  </button>
</template>
