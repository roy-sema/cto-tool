<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  content: string;
}>();

const contentHtml = computed(() => {
  const sanitizedHtml = props.content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return sanitizedHtml.replace(/`([^`]+)`/g, "<code>$1</code>");
});
</script>

<template>
  <div v-html="contentHtml" />
</template>

<style scoped>
:deep(code) {
  @apply break-all rounded-md bg-slate-100 px-1 text-cyan-600 dark:bg-slate-700;
}
</style>
