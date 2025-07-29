<script setup lang="ts">
import PaginationController from "@/aicm/components/common/PaginationController.vue";
import RuleTooltip from "@/aicm/components/common/RuleTooltip.vue";
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import AIUsage from "@/aicm/components/RepositoryGroup/AIUsage.vue";
import { getDevelopers } from "@/aicm/helpers/api";
import type { DeveloperGroup, DevelopersResponse } from "@/aicm/helpers/api.d";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/vue/24/solid";
import * as Sentry from "@sentry/vue";
import { Collapse, Popover, initTWE } from "tw-elements";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import DeveloperCell from "./DeveloperCell.vue";

const props = defineProps<{
  group: DeveloperGroup;
  useCollapsible: boolean;
  order: string;
  date: [Date, Date] | null;
}>();

// TODO cache values to avoid refetching
let developersPage = ref<DevelopersResponse>();
let isShown = false;

const isCollapsible = computed(() => props.useCollapsible && props.group.developers_count > 0);
const loading = ref(false);

const collapsibleAttributes = computed<any>(() => {
  if (isCollapsible.value) {
    return {
      "data-twe-collapse-init": true,
      "href": `#group-repos-${props.group.public_id}`,
      "aria-expanded": "false",
      "aria-controls": `group-repos-${props.group.public_id}`,
    };
  } else if (props.group.developers_count === 0) {
    return {
      "data-twe-toggle": "popover",
      "data-twe-trigger": "click focus hover",
      "data-twe-content": "Empty group",
    };
  }
  return {};
});

const aiData = computed(() => props.group);
const collapseRef = ref<HTMLElement | null>(null);

async function loadData(page = 1) {
  try {
    loading.value = true;
    const [since, until] = props.date ?? [null, null];
    const response = await getDevelopers(props.group.public_id, props.order, page, since, until);
    developersPage.value = response;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
}

async function collapseShown(event: Event) {
  isShown = true;
  loadData();
}

async function collapseHidden(event: Event) {
  isShown = false;
}

async function navigate(action: "first" | "prev" | "next" | "last") {
  let page = 1;
  if (action === "first") page = 1;
  else if (action === "prev") page = developersPage.value!.previous_page;
  else if (action === "next") page = developersPage.value!.next_page;
  else if (action === "last") page = developersPage.value!.total_pages;

  await loadData(page);
}

onMounted(() => {
  initTWE({ Collapse, Popover }, { allowReinits: true });

  if (collapseRef.value) {
    collapseRef.value.addEventListener("show.twe.collapse", collapseShown);
    collapseRef.value.addEventListener("hide.twe.collapse", collapseHidden);
  }
});

onBeforeUnmount(() => {
  if (collapseRef.value) {
    collapseRef.value.removeEventListener("show.twe.collapse", collapseShown);
    collapseRef.value.removeEventListener("hide.twe.collapse", collapseHidden);
  }
});

watch(
  () => props.order,
  async () => {
    // only fetch data if they are expanded
    if (isShown) await loadData();
  },
);
</script>

<template>
  <div
    class="developer-group mb-3 rounded-md border border-gray-200 bg-white p-4 dark:border-slate-600 dark:bg-slate-900"
  >
    <div
      class="flex cursor-pointer flex-col items-start gap-3 md:flex-row md:items-center md:justify-between md:gap-5"
      v-bind="collapsibleAttributes"
    >
      <div class="shrink-0">
        <div class="flex items-center gap-1 text-black dark:invert">
          <template v-if="isCollapsible">
            <ChevronRightIcon class="arrow-right inline w-3 md:w-4" />
            <ChevronDownIcon class="arrow-down inline w-3 md:w-4" />
          </template>

          <span class="text-sm font-semibold md:text-base"> {{ group.name }} ({{ group.developers_count }}) </span>
        </div>
        <div class="pt-1 text-xs text-gray-500">Analyzed: {{ group.stats?.code_num_lines || 0 }} lines</div>
      </div>

      <div class="flex grow flex-wrap gap-1 md:min-h-12">
        <template v-if="group.developers_count > 0">
          <RuleTooltip
            v-for="[rule, color] in group.rule_risk_list"
            :key="rule.public_id"
            :rule="rule"
            :color="color"
            :is_pill="true"
            placement="top"
          />
        </template>
      </div>
      <div v-if="group.developers_count > 0" class="shrink-0">
        <AIUsage
          :aiOverall="aiData.stats.percentage_ai_overall"
          :aiPure="aiData.stats.percentage_ai_pure"
          :aiBlended="aiData.stats.percentage_ai_blended"
          :human="aiData.stats.percentage_human"
          :num-lines="aiData.stats.code_num_lines"
        />
      </div>
    </div>

    <div
      :id="useCollapsible ? `group-repos-${group.public_id}` : undefined"
      ref="collapseRef"
      class="mt-3 border-t border-lightgrey dark:border-slate-600"
      :class="{ '!visible hidden': useCollapsible }"
      :data-te-collapse-item="useCollapsible ? true : undefined"
    >
      <div class="-mr-2 max-h-96 min-h-14 content-center overflow-y-auto overflow-x-hidden pr-2">
        <div v-if="loading" class="flex h-full items-center justify-center">
          <TWESpinner class="self-center" />
        </div>
        <template v-for="developer in developersPage?.developers" v-else :key="developer.public_id">
          <span
            class="block items-center justify-between rounded border-t border-lightgrey pl-4 first:border-0 dark:border-slate-600"
          >
            <DeveloperCell :developer="developer" />
          </span>
        </template>
      </div>
      <div v-if="!loading">
        <PaginationController :page_obj="developersPage" @navigate="navigate" />
      </div>
    </div>
  </div>
</template>
