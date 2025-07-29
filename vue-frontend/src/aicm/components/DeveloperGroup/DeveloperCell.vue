<script setup lang="ts">
import type { Developer } from "@/aicm/helpers/api.d";

const props = defineProps<{
  developer: Developer;
}>();
</script>

<template>
  <div class="developer flex items-center justify-between gap-5 py-2">
    <div class="text-sm font-semibold md:text-sm">
      {{ props.developer.name }}
    </div>
  </div>
</template>
