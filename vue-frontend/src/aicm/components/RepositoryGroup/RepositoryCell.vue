<script setup lang="ts">
import AIUsage from "@/aicm/components/RepositoryGroup/AIUsage.vue";
import TooltipProgressBar from "@/aicm/components/common/TooltipProgressBar.vue";
import type { Repository } from "@/aicm/helpers/api.d";
import { computed } from "vue";

const props = defineProps<{
  repository: Repository;
}>();

const dataSource = computed(() => {
  if (props.repository.until_commit) {
    return {
      ...props.repository.until_commit,
      ...props.repository.date_ai_fields,
      last_analysis_num_files: props.repository.until_commit.analysis_num_files,
    };
  }
  return props.repository;
});

const hasFiles = computed(() => dataSource.value.last_analysis_num_files > 0);
// only disable if the repository was not analyzed unrelated to the until_commit values
const isDisabled = computed(() => props.repository.code_num_lines === 0);
</script>

<template>
  <div class="py-2" :class="{ 'opacity-50': isDisabled }">
    <div class="repository mb-1 flex items-center justify-between gap-5">
      <div>
        <div class="text-sm font-semibold md:text-sm">
          {{ props.repository.full_name }}
        </div>
        <div class="mt-1 text-xs text-gray-500">
          <template v-if="hasFiles">
            <template v-if="dataSource.language_list_str"> {{ dataSource.language_list_str }} · </template>
            <template v-else-if="dataSource.last_analysis_num_files !== null">
              Analyzed: {{ dataSource.last_analysis_num_files }} files ·
            </template>
            Not evaluated: {{ dataSource.not_evaluated_num_files }} files
          </template>
          <template v-else>
            <span>There are no analyzed files in this repository</span>
          </template>
        </div>
      </div>

      <div class="shrink-0">
        <AIUsage
          :aiOverall="dataSource.percentage_ai_overall"
          :aiPure="dataSource.percentage_ai_pure"
          :aiBlended="dataSource.percentage_ai_blended"
          :human="dataSource.percentage_human"
          :numLines="dataSource.code_num_lines"
          size="sm"
        />
      </div>
    </div>

    <template v-if="repository.code_num_lines">
      <!-- TODO change this to dataSource when we make the attestation get properly affected by the range picker -->
      <TooltipProgressBar
        :title="`${repository.attested_num_lines} / ${repository.code_num_lines} lines attested`"
        content="This % is number of lines that has been attested divided by number of lines that can be attested. Not all code is attestable yet."
        :numerator="repository.attested_num_lines"
        :denominator="repository.code_num_lines"
      />
    </template>
  </div>
</template>
