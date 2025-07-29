<script setup lang="ts">
import type { Component } from "vue";

defineProps<{
  title?: string;
  icon?: Component;
  disabled?: boolean;
}>();

const emit = defineEmits(["click"]);
</script>

<template>
  <!-- TODO: is it worth using Primevue's Panel? -->
  <div
    class="rounded-lg bg-white p-6 shadow-sm dark:bg-slate-900"
    :class="{ 'opacity-75': disabled }"
    @click="emit('click')"
  >
    <slot name="header">
      <div class="mb-4 flex items-center space-x-3">
        <div v-if="icon" class="rounded-lg bg-sky-50 p-2 dark:bg-slate-700">
          <component :is="icon" class="size-6" />
        </div>
        <h3 class="font-semibold">{{ title }}</h3>
      </div>
    </slot>

    <slot />
  </div>
</template>
