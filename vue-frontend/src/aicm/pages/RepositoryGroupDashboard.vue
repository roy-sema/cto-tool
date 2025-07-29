<script setup lang="ts">
import Teleports from "@/aicm/components/common/Teleports.vue";
import RepositoryGroupCell from "@/aicm/components/RepositoryGroup/RepositoryGroupCell.vue";
import { getRepositoryGroups } from "@/aicm/helpers/api";
import type { RepositoryGroupDetail } from "@/aicm/helpers/api.d";
import type { IntegrationStatusMap } from "@/common/api.d";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import * as Sentry from "@sentry/vue";
import { subDays } from "date-fns";
import { onMounted, ref } from "vue";

const props = defineProps({
  orgFirstDate: { type: String, default: "" },
  defaultTimeWindowDays: { type: Number, required: true },
  updatedAt: { type: Number, default: 0 },
});

const loading = ref(true);
const dateLoading = ref(false);
const repositories = ref<RepositoryGroupDetail>({
  count: 0,
  groups: [],
  ungrouped: [],
});
const integrations = ref<IntegrationStatusMap>();
const updatedAt = ref(props.updatedAt);

const date = ref<[Date, Date] | null>(null);
const dateRange = ref<[Date, Date] | null>(null);

const loadData = async () => {
  try {
    loading.value = true;
    const until = new Date();
    const since = subDays(until, props.defaultTimeWindowDays);
    const response = await getRepositoryGroups(since.toISOString(), until.toISOString());
    repositories.value = response?.repositories;
    integrations.value = response.integrations;

    date.value = [since, until];
    dateRange.value = [since, until];
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const datePicked = async (newDate: [string, string] | null) => {
  if (newDate) {
    const [since, until] = newDate;
    dateLoading.value = true;
    try {
      repositories.value = (await getRepositoryGroups(since, until))?.repositories;
      dateRange.value = [new Date(since), new Date(until)];
    } catch (error) {
      Sentry.captureException(error);
    } finally {
      dateLoading.value = false;
    }
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <PageHeader
    title="GenAI Codebase Composition"
    :dateRange="dateRange"
    :integrations="integrations"
    :updatedAt="updatedAt"
    :loading="loading"
    class="-mx-4 -mt-4 lg:-mx-6"
  />

  <div>
    <div v-if="loading" class="mt-8 flex items-center justify-center">
      <ProgressSpinner />
    </div>
    <div v-else-if="repositories.count" class="mt-5">
      <div class="mb-4 md:flex md:items-end md:justify-between">
        <div>
          <h2 class="text-xl font-semibold">By Repository Group ({{ repositories.count }})</h2>
          <a
            href="/genai-radar/developer-groups/"
            class="mt-2 text-xs font-semibold text-blue hover:text-violet dark:hover:text-lightgrey"
          >
            View by Developer Group <sup>BETA</sup>
          </a>
        </div>
        <RangeDatePicker :date="date" :firstDate="orgFirstDate" @update:date="datePicked" />
      </div>

      <RepositoryGroupCell
        v-for="group in repositories.groups"
        :key="group.public_id"
        :group="group"
        :useCollapsible="true"
      />
      <RepositoryGroupCell
        v-if="repositories.ungrouped.repositories.length > 0"
        :group="repositories.ungrouped"
        :useCollapsible="repositories.groups.length > 0"
      />
    </div>
    <div v-else>
      <p class="mt-5">There are no repositories yet, did you connect any provider ?</p>
    </div>

    <Teleports />
  </div>
</template>
