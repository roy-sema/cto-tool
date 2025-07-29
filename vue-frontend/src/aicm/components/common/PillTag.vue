<script setup lang="ts">
const props = defineProps<{
  text: string;
  color?: string;
}>();
</script>

<template>
  <div>
    <span
      class="inline-block whitespace-nowrap rounded-full px-3 py-1 text-xs"
      :class="{
        [props.color || '']: props.color,
        'bg-gray-200 dark:bg-slate-600': !props.color,
      }"
    >
      {{ text }}
    </span>
  </div>
</template>
