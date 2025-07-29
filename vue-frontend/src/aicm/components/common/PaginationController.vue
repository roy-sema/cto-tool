<script lang="ts" setup>
import type { PaginatedResponse } from "@/aicm/helpers/api.d";

defineProps<{
  page_obj: PaginatedResponse | undefined;
}>();

const emit = defineEmits<{
  (event: "navigate", payload: "first" | "prev" | "next" | "last"): void;
}>();

function emitEvent(action: "first" | "prev" | "next" | "last") {
  emit("navigate", action);
}
</script>

<template>
  <div v-if="page_obj && page_obj.total_pages > 1" class="text-center text-sm">
    <span :class="{ invisible: !page_obj.previous_page }">
      <a class="navigator mx-2" @click="emitEvent('first')"> &laquo; First </a>
      <a class="navigator" @click="emitEvent('prev')">Prev</a>
    </span>

    <span class="mx-4">Page {{ page_obj.current_page }} of {{ page_obj.total_pages }}</span>

    <span :class="{ invisible: !page_obj.next_page }">
      <a class="navigator mx-2" @click="emitEvent('next')">Next</a>
      <a class="navigator" @click="emitEvent('last')">Last &raquo; </a>
    </span>
  </div>
</template>

<style scoped>
.navigator {
  @apply cursor-pointer text-blue hover:text-violet dark:hover:text-lightgrey;
}
</style>
