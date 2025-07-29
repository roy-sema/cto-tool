<script setup lang="ts">
import AttestationProgressBar from "@/aicm/components/common/AttestationProgressBar.vue";
import SwitchInput from "@/aicm/components/common/SwitchInput.vue";
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import { attestChunkAgreeAll } from "@/aicm/helpers/api";
import type { RepositoryFile, RepositoryFileChunk } from "@/aicm/helpers/api.d";
import * as Sentry from "@sentry/vue";
import { computed, ref, watch } from "vue";

const props = defineProps<{
  repositoryId: string;
  repositoryFullName: string;
  selectedFiles: RepositoryFile[];
  codeGenerationLabels: { [key: string]: string };
  selectedChunks: RepositoryFileChunk[];
}>();

const emit = defineEmits(["attestedAll", "filterChanged", "blameChanged"]);

// Local state while there's a request to fetch the chunks after agreeing to all.
// Prevents the progress and button to show a wrong number of attested chunks right after agreeing all.
const attestedAll = ref(false);

const loading = ref(false);
const subTitle = computed(() =>
  props.selectedFiles.length > 1
    ? `Analyzed files (${props.selectedFiles.length})`
    : props.selectedFiles[0]?.relative_path || "",
);

let selected_labels = ref(Object.keys(props.codeGenerationLabels));
let showBlame = ref(true);

watch(selected_labels, (new_value) => emit("filterChanged", new_value));
watch(showBlame, (new_value) => emit("blameChanged", new_value));

const handleAgreeAll = async () => {
  if (loading.value) {
    return;
  }

  loading.value = true;

  const attestations = attestableChunks.value
    .filter((chunk) => !chunk.attestation)
    .map((chunk) => ({ code_hash: chunk.code_hash, label: chunk.label }));
  try {
    await attestChunkAgreeAll(props.repositoryId, attestations);
    emit("attestedAll");
    attestedAll.value = true;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

const attestableChunks = computed(() => {
  return props.selectedChunks.filter((chunk) => chunk.label !== "not_evaluated");
});
const numSelectedChunksAttested = computed(() => {
  return attestableChunks.value.filter((chunk) => chunk.attestation).length;
});
const numSelectedChunksTotal = computed(() => {
  return attestableChunks.value.length;
});
const allSelectedChunksAttested = computed(() => {
  return numSelectedChunksAttested.value === numSelectedChunksTotal.value;
});

watch(
  () => props.selectedChunks,
  () => {
    // Reset local state when the selected chunks update
    attestedAll.value = false;
  },
);
</script>

<template>
  <div class="sticky top-0 flex flex-col justify-between bg-gray-50 py-3 pt-5 dark:bg-slate-800 xl:flex-row">
    <div class="mb-4 mr-2">
      <h3 class="break-all text-lg font-semibold md:text-lg">{{ repositoryFullName }}</h3>
      <h4 class="break-all text-sm">{{ subTitle }}</h4>
    </div>
    <div class="flex flex-col justify-end gap-3 md:flex-row">
      <div v-if="attestableChunks.length">
        <div class="flex justify-end gap-3">
          <div class="flex flex-col items-center gap-0.5">
            <div class="text-bold mb-1 whitespace-nowrap text-sm">
              {{ attestedAll ? numSelectedChunksTotal : numSelectedChunksAttested }} /
              {{ numSelectedChunksTotal }} chunks attested
            </div>
            <div class="w-40">
              <AttestationProgressBar
                :progress="attestedAll ? numSelectedChunksTotal : numSelectedChunksAttested"
                :max="numSelectedChunksTotal"
              />
            </div>
          </div>
          <div v-if="!allSelectedChunksAttested && !attestedAll">
            <button
              class="whitespace-nowrap rounded-md bg-blue px-3 py-1.5 text-sm font-semibold leading-6 text-white shadow-sm"
              :class="{
                'hover:bg-violet focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue dark:hover:bg-pink':
                  !loading,
                'cursor-not-allowed opacity-80': loading,
              }"
              :disabled="loading"
              @click="handleAgreeAll"
            >
              <TWESpinner v-if="loading" :size="4" class="ml-[4em] mr-[4em]" /><span v-else>Agree all remaining</span>
            </button>
          </div>
        </div>
      </div>
      <div class="flex flex-col items-end">
        <div class="w-64">
          <select
            id="label-filter"
            v-model="selected_labels"
            data-te-select-init
            data-te-select-displayed-labels="3"
            multiple
          >
            <option v-for="[key, label] in Object.entries(codeGenerationLabels)" :key="key" :value="key">
              {{ label }}
            </option>
          </select>
          <!-- HACK z=10 to have it appear on top of the select border on first render -->
          <label class="z-10" for="label-filter" data-te-select-label-ref>Filter</label>
        </div>
        <div class="relative mt-2 self-end">
          <SwitchInput id="blameSwitch" v-model="showBlame" />
          <label class="inline-block ps-[0.15rem] text-sm hover:cursor-pointer" for="blameSwitch"> Author </label>
        </div>
      </div>
    </div>
  </div>
</template>
