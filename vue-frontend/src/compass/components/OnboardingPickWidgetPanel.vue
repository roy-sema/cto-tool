<script setup lang="ts">
import { CheckCircleIcon } from "@heroicons/vue/24/outline";
import type { FunctionalComponent, SVGAttributes } from "vue";

defineProps<{
  header: string;
  subHeader: string;
  availableInsights: string[];
  connectAction: () => void;
  Logo: FunctionalComponent<SVGAttributes>;
}>();
</script>

<template>
  <Panel>
    <template #header>
      <div>
        <div class="flex flex-row items-center">
          <Logo class="size-4" />
          <p class="ml-2 font-bold">{{ header }}</p>
        </div>
        <p class="text-sm text-gray-500">{{ subHeader }}</p>
      </div>
    </template>
    <template #default>
      <p class="text-sm font-bold">Available insights:</p>
      <div v-for="(insight, index) in availableInsights" :key="index" class="mt-2 flex flex-row">
        <CheckCircleIcon class="size-6 text-green-600" />
        <p class="ml-2 text-sm text-gray-500">{{ insight }}</p>
      </div>
      <Button
        label="Connect"
        size="small"
        severity="secondary"
        variant="outlined"
        class="mt-2 w-full"
        @click="connectAction"
      />
    </template>
  </Panel>
</template>
