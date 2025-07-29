<script setup lang="ts">
import LineMiniChart from "@/aicm/components/common/LineMiniChart.vue";
import PillTag from "@/aicm/components/common/PillTag.vue";
import RuleTooltip from "@/aicm/components/common/RuleTooltip.vue";
import TooltipProgressBar from "@/aicm/components/common/TooltipProgressBar.vue";
import AIUsage from "@/aicm/components/RepositoryGroup/AIUsage.vue";
import RepositoryCell from "@/aicm/components/RepositoryGroup/RepositoryCell.vue";
import type { RepositoryGroup } from "@/aicm/helpers/api.d";
import { QuestionMarkCircleIcon } from "@heroicons/vue/24/outline";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/vue/24/solid";
import { Collapse, Popover, initTWE } from "tw-elements";
import { computed, onMounted } from "vue";
import ROIPanel from "./ROIPanel.vue";

const props = defineProps<{
  group: RepositoryGroup;
  useCollapsible: boolean;
}>();

const isCollapsible = computed(() => props.useCollapsible && props.group.repositories.length > 0);

const collapsibleAttributes = computed<any>(() => {
  if (isCollapsible.value) {
    return {
      "data-twe-collapse-init": true,
      "href": `#group-repos-${props.group.public_id}`,
      "aria-expanded": "false",
      "aria-controls": `group-repos-${props.group.public_id}`,
    };
  } else if (props.group.repositories.length === 0) {
    return {
      "data-twe-toggle": "popover",
      "data-twe-trigger": "click focus hover",
      "data-twe-content": "Empty group",
    };
  }
  return {};
});

const aiData = computed(() => props.group.date_ai_fields);
const numFiles = computed(() =>
  aiData.value.num_files !== undefined ? aiData.value.num_files : props.group.num_files,
);
const hasFiles = computed(() => numFiles.value > 0);
const hasRepos = computed(() => props.group.repositories.length > 0);
const showROIPanel = computed(() => props.group.roi_enabled && hasRepos.value && hasFiles.value);
const hasCharts = computed(() => props.group.charts_cumulative.length > 0 && props.group.charts_daily.length > 0);
const showAttestations = computed(() => props.group.code_num_lines > 0 && hasFiles.value);

onMounted(() => initTWE({ Collapse, Popover }, { allowReinits: true }));
</script>

<template>
  <div
    class="repository-group mb-3 cursor-pointer rounded-md border border-gray-200 bg-white p-4 dark:border-slate-600 dark:bg-slate-900"
  >
    <div
      class="mb-2 flex flex-col items-start gap-3 md:flex-row md:items-center md:justify-between md:gap-5"
      v-bind="collapsibleAttributes"
    >
      <div class="shrink-0">
        <div class="flex items-center gap-1 text-black dark:invert">
          <template v-if="isCollapsible">
            <ChevronRightIcon class="arrow-right inline w-3 md:w-4" />
            <ChevronDownIcon class="arrow-down inline w-3 md:w-4" />
          </template>

          <span class="text-sm font-semibold md:text-base"> {{ group.name }} ({{ group.repositories.length }}) </span>
        </div>
        <div class="pt-1 text-xs text-gray-500">Not evaluated: {{ aiData.not_evaluated_num_files }} files</div>
      </div>

      <div class="flex grow flex-wrap gap-1 md:min-h-12">
        <PillTag v-if="group.usage_category" :text="group.usage_category" />
        <template v-if="hasRepos">
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
      <div v-if="group.repositories.length > 0" class="shrink-0">
        <AIUsage
          :aiOverall="aiData.percentage_ai_overall.toFixed(0)"
          :aiPure="aiData.percentage_ai_pure.toFixed(0)"
          :aiBlended="aiData.percentage_ai_blended.toFixed(0)"
          :human="aiData.percentage_human.toFixed(0)"
          :num-lines="aiData.code_num_lines"
        />
      </div>
    </div>

    <!-- TODO change this so it uses aiData when we make the attestation get properly affected by the range picker -->
    <TooltipProgressBar
      v-if="showAttestations"
      :title="`${props.group.attested_num_lines} / ${props.group.code_num_lines} lines attested`"
      content="This % is number of lines that has been attested divided by number of lines that can be attested. Not all code is attestable yet."
      :numerator="props.group.attested_num_lines"
      :denominator="props.group.code_num_lines"
    />

    <ROIPanel
      v-if="showROIPanel"
      :productivityAchievement="group.productivity_achievement"
      :potentialProductivityCaptured="group.potential_productivity_captured"
      :costSaved="group.cost_saved"
      :hoursSaved="group.hours_saved"
      :toolsCostSavedPercentage="group.tools_cost_saved_percentage"
      :debugData="group.debug_data"
      class="mt-3 cursor-auto"
    />

    <div
      :id="useCollapsible ? `group-repos-${group.public_id}` : undefined"
      class="mt-3 cursor-auto border-t border-lightgrey dark:border-slate-600"
      :class="{ '!visible hidden': useCollapsible }"
      :data-te-collapse-item="useCollapsible ? true : undefined"
    >
      <div v-if="hasCharts" class="my-5">
        <div class="my-2 md:text-xl">
          Cumulative usage <sup>BETA</sup>
          <div
            class="ml-1 inline-block"
            data-twe-toggle="popover"
            data-twe-content="Composition of all the code, up to that day"
            data-twe-trigger="hover focus"
          >
            <QuestionMarkCircleIcon class="inline w-5 cursor-help opacity-80" />
          </div>
        </div>
        <div class="grid gap-5 md:grid-cols-3">
          <LineMiniChart
            v-for="chart in group.charts_cumulative"
            :id="chart.id"
            :key="chart.id"
            :title="chart.label + ' (%)'"
            :data="chart.data"
          />
        </div>
        <div class="my-2 md:text-xl">
          Usage in Time Period <sup>BETA</sup>
          <div
            class="ml-1 inline-block"
            data-twe-toggle="popover"
            data-twe-content="Composition of all pushed code on that day"
            data-twe-trigger="hover focus"
          >
            <QuestionMarkCircleIcon class="inline w-5 cursor-help opacity-80" />
          </div>
        </div>
        <div class="grid gap-5 md:grid-cols-3">
          <LineMiniChart
            v-for="chart in group.charts_daily"
            :id="chart.id"
            :key="chart.id"
            :title="chart.label + ' (%)'"
            :data="chart.data"
          />
        </div>
      </div>

      <div class="-mr-2 max-h-96 overflow-y-auto overflow-x-hidden pr-2">
        <template v-for="repository in group.repositories" :key="repository.public_id">
          <a
            v-if="repository.code_num_lines"
            :href="`/genai-radar/repositories/${repository.public_id}/`"
            class="block rounded pl-4 hover:bg-lightgrey dark:hover:bg-slate-700"
          >
            <RepositoryCell :repository="repository" />
          </a>
          <span v-else class="block rounded pl-4 hover:bg-lightgrey dark:hover:bg-slate-700">
            <RepositoryCell :repository="repository" />
          </span>
        </template>
      </div>
    </div>
  </div>
</template>
