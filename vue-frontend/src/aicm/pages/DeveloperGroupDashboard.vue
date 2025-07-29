<script setup lang="ts">
import Teleports from "@/aicm/components/common/Teleports.vue";
import DeveloperGroupCell from "@/aicm/components/DeveloperGroup/DeveloperGroupCell.vue";
import { getDeveloperGroups } from "@/aicm/helpers/api";
import type { DeveloperGroup } from "@/aicm/helpers/api.d";
import type { IntegrationStatusMap } from "@/common/api.d";
import RangeDatePicker from "@/common/components/RangeDatePicker.vue";
import PageHeader from "@/compass/components/common/PageHeader.vue";
import { ArrowDownTrayIcon, QuestionMarkCircleIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { subDays } from "date-fns";
import { Popover, initTWE } from "tw-elements";
import { onMounted, ref } from "vue";

const props = defineProps({
  developersCount: { type: Number, required: true },
  mergeDevelopersUrl: { type: String, required: true },
  orgFirstDate: { type: String, default: "" },
  defaultTimeWindowDays: { type: Number, required: true },
  updatedAt: { type: Number, default: 0 },
});

const loading = ref(true);
const dateLoading = ref(false);
const developerGroups = ref<DeveloperGroup[]>([]);
const order = ref("name");
const integrations = ref<IntegrationStatusMap>();
const updatedAt = ref(props.updatedAt);

const until = new Date();
const since = subDays(until, props.defaultTimeWindowDays);
const date = ref<[Date, Date] | null>([since, until]);
const dateRange = ref<[Date, Date] | null>([since, until]);

const loadData = async (update = false, since: Date | null = null, until: Date | null = null) => {
  try {
    if (!update) loading.value = true;
    const response = await getDeveloperGroups(since, until);
    developerGroups.value = response.groups;
    integrations.value = response.integrations;

    if (since && until) {
      dateRange.value = [new Date(since), new Date(until)];
    }
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    if (!update) loading.value = false;
  }
};

const datePicked = async (newDate: [Date, Date] | null) => {
  if (newDate) {
    const [since, until] = newDate;
    date.value = newDate;
    dateLoading.value = true;
    try {
      await loadData(true, since, until);
    } catch (error) {
      Sentry.captureException(error);
    } finally {
      dateLoading.value = false;
    }
  }
};

onMounted(() => {
  loadData();
  initTWE({ Popover }, { allowReinits: true });
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
    <div v-show="loading" class="mt-16 flex items-center justify-center">
      <ProgressSpinner />
    </div>
    <div v-show="!loading && developerGroups.length" class="mt-5">
      <div class="mb-4 md:flex md:items-center md:justify-between">
        <div>
          <h2 class="content-end text-xl font-semibold">
            By Developer Group ({{ developersCount }})<sup class="mx-2">BETA</sup>
            <span
              class="w-5 cursor-help opacity-80 dark:invert"
              data-twe-toggle="popover"
              data-twe-placement="top"
              data-twe-html="true"
              data-twe-content="Based on all pushed code in the selected date range."
              data-twe-trigger="hover focus"
            >
              <QuestionMarkCircleIcon class="inline w-5 cursor-help opacity-80 dark:invert" />
            </span>
          </h2>
          <div class="mt-2 flex items-center">
            <a
              href="/genai-radar/developer-groups/export/"
              class="flex items-center gap-1 text-xs font-semibold text-blue hover:text-violet dark:hover:text-lightgrey"
            >
              <ArrowDownTrayIcon class="w-4" />
              Export
            </a>
            <span class="mx-2 text-xs">|</span>
            <a
              href="/genai-radar/repository-groups/"
              class="text-xs font-semibold text-blue hover:text-violet dark:hover:text-lightgrey"
            >
              View by Repository Group
            </a>
          </div>
        </div>
        <RangeDatePicker :date="date" :firstDate="orgFirstDate" @update:date="datePicked" />
      </div>
      <DeveloperGroupCell
        v-for="group in developerGroups"
        :key="group.public_id"
        :group="group"
        :useCollapsible="true"
        :order="order"
        :date="date"
      />
      <div class="mb-4 text-right text-sm">
        Do you see repeated developers? Try
        <a class="font-semibold text-blue hover:text-violet dark:hover:text-lightgrey" :href="mergeDevelopersUrl">
          merging them
        </a>
      </div>
    </div>
    <div v-show="!loading && !developerGroups.length">
      <p class="mt-5">There are no developers data yet.</p>
    </div>

    <Teleports />
  </div>
</template>
