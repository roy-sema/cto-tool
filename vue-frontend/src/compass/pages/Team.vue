<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import TeamHealthItem from "@/compass/components/TeamHealthItem.vue";
import { getTeamHealthData } from "@/compass/helpers/api";
import type { TeamHealthMetric } from "@/compass/helpers/api.d";
import { CheckCircleIcon, MagnifyingGlassIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { computed, onMounted, ref } from "vue";

const loading = ref(true);
const updatedAt = ref();
const integrations = ref<IntegrationStatusMap>();
const metrics = ref<TeamHealthMetric[]>();
const summary = ref<string>();
const insights = ref<string[]>();
const searchText = ref("");

const loadData = async () => {
  try {
    loading.value = true;

    const response = await getTeamHealthData();

    updatedAt.value = response.updated_at;
    integrations.value = response.integrations;
    metrics.value = response.metrics;
    summary.value = response.summary;
    insights.value = response.insights;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const metricsFiltered = computed(() => {
  if (searchText.value === "") return metrics.value;
  return metrics.value?.filter((metric) => {
    return metric.name.toLocaleLowerCase().includes(searchText.value.trim().toLocaleLowerCase());
  });
});

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader title="Team Health" :updatedAt="updatedAt" :integrations="integrations" :loading="loading" />

  <div class="flex flex-col justify-between gap-5 px-4 py-5 lg:px-6 xl:flex-row">
    <div class="shrink-0 rounded-md xl:w-2/3">
      <Panel class="no-header-panel">
        <div class="flex flex-col gap-5">
          <div v-if="loading" class="flex items-center justify-center">
            <ProgressSpinner />
          </div>
          <div v-else-if="!metrics?.length" class="flex items-center justify-center">
            <p class="text-sm">There are no metrics.</p>
          </div>
          <template v-else>
            <IconField class="w-full">
              <InputIcon> <MagnifyingGlassIcon class="size-4" /> </InputIcon>
              <InputText v-model="searchText" placeholder="Search" class="w-full" />
            </IconField>
            <div v-if="!metrics || metricsFiltered?.length == 0" class="flex items-center justify-center">
              <p class="text-sm">There are no metrics that matches your query</p>
            </div>
            <template v-for="metric in metricsFiltered" :key="metric.name">
              <TeamHealthItem :metric="metric" />
            </template>
          </template>
        </div>
      </Panel>
    </div>
    <div class="flex grow flex-col gap-5">
      <Panel>
        <template #header>
          <div class="flex w-full justify-between">
            <h3 class="text-md font-semibold">Summary</h3>
            <Tag severity="info" value="AI" class="!text-xs !font-normal" />
          </div>
        </template>

        <div v-if="loading" class="flex items-center justify-center">
          <ProgressSpinner />
        </div>
        <div v-else>
          <p class="break-words text-sm font-normal text-muted-color">{{ summary || "There is no summary." }}</p>
        </div>
      </Panel>

      <div>
        <Panel>
          <template #header>
            <div class="flex w-full justify-between">
              <h3 class="text-md font-semibold">Insights</h3>
              <Tag severity="info" value="AI" class="!text-xs !font-normal" />
            </div>
          </template>

          <div v-if="loading" class="flex items-center justify-center">
            <ProgressSpinner />
          </div>
          <div v-else-if="!insights?.length">
            <p class="text-sm">There are no insights.</p>
          </div>
          <div v-else>
            <div v-for="(insight, index) in insights" :key="index">
              <Divider v-if="index > 0" />
              <div class="flex items-start gap-2">
                <CheckCircleIcon class="mt-0.5 size-4 min-w-4 text-green-700" />
                <p class="break-words text-sm font-normal text-muted-color">{{ insight }}</p>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  </div>
</template>
