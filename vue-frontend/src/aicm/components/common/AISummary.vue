<script setup lang="ts">
import RuleList from "@/aicm/components/common/RuleList.vue";
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import {
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/vue/24/outline";

const props = withDefaults(
  defineProps<{
    aiComposition: any; // TODO: add type for aiComposition
    isPullRequest?: boolean;
    numAnalyzedFiles?: number;
    numNotEvaluatedFiles?: number;
    evaluatedPercentage?: number;
    loading?: boolean;
    size?: string;
    trend?: boolean;
  }>(),
  {
    isPullRequest: false,
    numAnalyzedFiles: 0,
    numNotEvaluatedFiles: 0,
    evaluatedPercentage: 0,
    trend: false,
  },
);

const numColumns = Object.keys(props.aiComposition).length;
const gridClass = `grid md:grid-cols-${numColumns} gap-5`;
const smallSize = props.size === "sm";
</script>

<template>
  <div>
    <div class="mt-5" :class="gridClass">
      <div
        v-for="aiType in props.aiComposition"
        :key="aiType.label"
        :class="`rounded-xl border border-gray-200 p-4 dark:border-slate-600 risk-gradient-${aiType.color} relative`"
      >
        <TWESpinner v-if="loading" :size="4" class="absolute right-2 top-2 opacity-80" />
        <div class="justify-left flex gap-1 font-semibold">
          <span :class="smallSize ? 'text-sm' : 'text-base'">
            {{ aiType.label }}
          </span>
          <div
            class="leading-5"
            data-te-toggle="popover"
            :data-te-title="aiType.title"
            :data-te-content="aiType.desc"
            data-te-trigger="hover focus"
          >
            <QuestionMarkCircleIcon class="inline w-4 cursor-help opacity-80" />
          </div>
        </div>
        <div class="mt-2 flex items-center gap-3">
          <div
            v-if="props.trend"
            class="inline-block h-10 w-10 shrink-0 rounded-full bg-lightgrey dark:bg-slate-600 xl:h-11 xl:w-11"
          >
            <div class="flex h-full items-center justify-center">
              <template v-if="aiType.value == aiType.previous_value">
                <ArrowLeftIcon class="w-3 xl:w-4" />
                <ArrowRightIcon class="w-3 xl:w-4" />
              </template>
              <ArrowUpIcon
                v-else-if="aiType.value > aiType.previous_value"
                class="w-4 opacity-60 dark:opacity-80 xl:w-5"
              />
              <ArrowDownIcon v-else class="w-4 opacity-60 dark:opacity-80 xl:w-5" />
            </div>
          </div>

          <div
            :class="
              `font-semibold risk-text-${aiType.color}` +
              ' ' +
              (smallSize ? 'text-4xl xl:text-5xl' : 'text-5xl xl:text-6xl')
            "
          >
            <span>{{ aiType.whole }}</span>
            <span v-if="aiType.decimal" :class="props.size == 'sm' ? 'text-xs xl:text-sm' : 'text-sm xl:text-base'"
              >.{{ aiType.decimal }}</span
            >
            <span>%</span>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-5 text-center opacity-80" :class="smallSize ? 'text-xs' : 'text-sm'">
      <template v-if="props.isPullRequest">
        Analyzed: {{ props.numAnalyzedFiles }} files · Not evaluated: {{ props.numNotEvaluatedFiles }} files
      </template>
      <template v-else-if="props.evaluatedPercentage"> {{ props.evaluatedPercentage }}% of code evaluated </template>
    </div>

    <div class="md:mt-5" :class="gridClass">
      <div v-for="aiType in aiComposition" :key="aiType.label">
        <template v-if="aiType.rules.length">
          <div class="mb-2 font-bold md:hidden">{{ aiType.label }}</div>
          <RuleList :rules="aiType.rules" />
        </template>
      </div>
    </div>
  </div>
</template>
