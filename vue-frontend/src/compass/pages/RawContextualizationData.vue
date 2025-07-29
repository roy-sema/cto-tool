<script setup lang="ts">
import PageHeader from "@/compass/components/common/PageHeader.vue";
import { getRawContextualizationData } from "@/compass/helpers/api";
import * as Sentry from "@sentry/vue";
import { onMounted, ref } from "vue";

const loading = ref(true);
const data = ref<string>();

const loadData = async () => {
  try {
    loading.value = true;
    const response = await getRawContextualizationData();
    data.value = response;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader title="Raw Results" :updatedAt="null" :beta="true" />
  <div class="sip mx-auto mt-5 flex w-screen max-w-screen-xl flex-col gap-4 px-4 md:w-full">
    <ProgressSpinner v-if="loading" class="!size-14" />
    <div
      v-else-if="data"
      class="scroll-container overflow-y-scroll whitespace-pre rounded-md border border-gray-200 bg-white p-4 shadow-md dark:border-slate-600 dark:bg-slate-900"
    >
      {{ data }}
    </div>
    <div v-else class="text-gray-500">An Error has occurred while loading the data</div>
  </div>
</template>

<style scoped lang="scss">
.scroll-container {
  --topbar-height: 210px;
  max-height: calc(100vh - var(--topbar-height) - 1.25rem);
}
</style>
