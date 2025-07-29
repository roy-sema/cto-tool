<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import Integrations from "@/compass/components/Integrations.vue";

defineProps<{
  integrations: IntegrationStatusMap;
}>();
</script>

<template>
  <div class="rounded-md border border-cyan-600 bg-cyan-50 px-2 py-1 dark:bg-cyan-950">
    <div class="text-sm text-cyan-600">Integrations</div>
    <Integrations :integrations="integrations" class="mt-2 h-12 flex-col flex-wrap gap-2" />
  </div>
</template>
