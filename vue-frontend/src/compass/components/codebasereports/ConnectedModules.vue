<script setup lang="ts">
import { CheckCircleIcon } from "@heroicons/vue/24/outline";

interface Module {
  name: string;
  icon: string;
  connected: boolean;
}

interface Modules {
  [module_type: string]: Record<string, Module>;
}

defineProps<{
  modules: Record<string, Modules>;
}>();
</script>

<template>
  <div class="grid gap-5 sm:grid-cols-2">
    <div v-for="(type_modules, module_type) in modules" :key="module_type">
      <div class="font-bold">{{ module_type }}</div>
      <div
        v-for="module in type_modules"
        class="my-3 flex items-center justify-between rounded-xl border border-lightgrey p-2 shadow-md dark:border-slate-600"
      >
        <span class="flex items-center gap-2">
          <img :src="`/static/${module.icon}`" class="inline-block size-5" />
          {{ module.name }}
        </span>
        <span v-if="module.connected" class="text-level-green flex items-center gap-1 text-sm font-semibold">
          Connected <CheckCircleIcon class="inline size-4" />
        </span>
        <a
          v-else
          href="/settings/connections"
          class="text-sm font-semibold text-blue hover:text-violet dark:hover:text-lightgrey"
          >Setup</a
        >
      </div>
    </div>
  </div>
</template>
