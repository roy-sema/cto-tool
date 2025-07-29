<script setup lang="ts">
import SimplePanel from "@/compass/components/sip/SimplePanel.vue";
import type { Component } from "vue";

defineProps<{
  title?: string;
  icon?: Component;
  disabled?: boolean;
}>();

const emit = defineEmits(["click"]);
</script>

<template>
  <SimplePanel
    :title="title"
    :icon="icon"
    :disabled="disabled"
    class="cursor-pointer transition-all duration-200"
    :class="{ 'hover:shadow-md dark:hover:shadow-slate-700': !disabled }"
    @click="emit('click')"
  >
    <template #default>
      <slot />
    </template>
    <template #header>
      <slot name="header" />
    </template>
  </SimplePanel>
</template>
