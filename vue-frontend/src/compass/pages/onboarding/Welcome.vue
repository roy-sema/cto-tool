<script setup lang="ts">
import { Activity, Brain, LineChart } from "lucide-vue-next";
import { useRouter } from "vue-router";

const router = useRouter();
</script>

<template>
  <div class="centered-wrapper p-5">
    <Card>
      <template #title>
        <div class="m-5 text-center">
          <h1 class="mb-2">Welcome to the MVP of the Sema Intelligence Platform</h1>
          <p>Here's what to expect from onboarding:</p>
        </div>
      </template>
      <template #content>
        <div class="m-5">
          <p class="mb-2">1. You can connect one or more of your version control systems.</p>
          <p>2. Based on version control system only, you will start seeing results for three SIP modules:</p>
          <div class="flex flex-col justify-center gap-8 p-5 sm:flex-row">
            <div class="flex items-center gap-x-2">
              <component :is="Activity" class="size-8 rounded-md border border-gray-400 p-1" />
              <p class="font-bold">Engineering Radar</p>
            </div>
            <div class="flex items-center gap-x-2">
              <component :is="Brain" class="size-8 rounded-md border border-gray-400 p-1" />
              <p class="font-bold">GenAI Radar</p>
            </div>
            <div class="flex items-center gap-x-2">
              <component :is="LineChart" class="size-8 rounded-md border border-gray-400 p-1" />
              <p class="font-bold">Product Roadmap Radar</p>
            </div>
          </div>
          <p class="mb-4">3. For most of these modules, processing will take overnight for the first time.</p>
          <p>
            Questions or comments? We'd love to hear from you.
            <a href="/contact" class="text-blue underline">Click here</a>
          </p>
        </div>
      </template>
      <template #footer>
        <div class="text-center">
          <Button label="Next" @click="router.push({ name: 'onboarding-connect-vcs' })" />
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
:deep(.p-card) {
  @apply bg-gray-300 text-black dark:bg-gray-700 dark:text-white;
}
</style>
