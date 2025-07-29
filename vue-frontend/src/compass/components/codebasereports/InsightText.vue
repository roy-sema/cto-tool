<script setup lang="ts">
defineProps<{
  level: string;
  status: string;
  text: string;
  description?: string;
}>();
</script>

<template>
  <div class="insight-container">
    <div class="mb-5 rounded-xl border border-lightgrey p-4 text-sm shadow-md dark:border-slate-600">
      <p>
        {{ text }} <span class="font-bold" :class="`text-level-${level}`">{{ status }}</span
        >.
      </p>
      <p v-if="description" class="mt-2 text-sm">{{ description }}</p>
    </div>
  </div>
</template>
