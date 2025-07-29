<script setup lang="ts">
import FileChunk from "@/aicm/components/FileViewer/FileChunk.vue";
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import type { RepositoryFile } from "@/aicm/helpers/api.d";
import { ChevronDoubleLeftIcon, ChevronDownIcon, ChevronRightIcon } from "@heroicons/vue/16/solid";
import { Collapse, initTWE } from "tw-elements";
import { computed, nextTick, watch } from "vue";

const props = defineProps<{
  files: RepositoryFile[];
  repositoryId: string;
  selectedFilters: string[];
  codeGenerationLabels: { [key: string]: string };
  attestationLabels: { [key: string]: string };
  chunkLoading: boolean;
  showBlame?: boolean;
  loadingMoreFiles?: boolean;
}>();

const emit = defineEmits(["attested", "filteredChunkedFiles"]);

const filteredChunkedFiles = computed(() => {
  return props.files.map((file) => ({
    ...file,
    chunks: file.chunks.filter((chunk) => props.selectedFilters.includes(chunk.label)),
  }));
});

watch(filteredChunkedFiles, (newFilteredChunkedFiles) => {
  nextTick(() => initTWE({ Collapse }));
  emit("filteredChunkedFiles", newFilteredChunkedFiles);
});
</script>

<template>
  <div v-for="file in filteredChunkedFiles" :key="file.public_id" class="analyzed-files mb-3 mt-5 max-w-full">
    <div
      v-if="filteredChunkedFiles.length > 1"
      class="flex cursor-pointer items-center gap-1"
      aria-expanded="true"
      data-twe-collapse-init
      :href="`#file-chunks-${file.public_id}`"
      :aria-controls="`file-chunks-${file.public_id}`"
    >
      <ChevronRightIcon class="arrow-right inline w-3 md:w-4" />
      <ChevronDownIcon class="arrow-down inline w-3 md:w-4" />

      <span class="text-sm font-semibold">{{ file.relative_path }}</span>
    </div>

    <div :id="`file-chunks-${file.public_id}`" class="!visible mt-3" data-twe-collapse-item data-twe-collapse-show>
      <div v-if="chunkLoading" class="mt-16 text-center">
        <TWESpinner />
      </div>

      <div v-else>
        <FileChunk
          v-for="chunk in file.chunks"
          :key="`${file.public_id}-${chunk.public_id}`"
          :chunk="chunk"
          :codeGenerationLabels
          :attestationLabels
          :repositoryId="props.repositoryId"
          :showBlame="props.showBlame"
          :shredded="file.shredded"
          @attested="emit('attested', { file, chunk, ...$event })"
        />

        <div v-show="!file.chunks.length && !file.not_evaluated">
          <div class="text-xs">No chunks match the current filters.</div>
        </div>

        <div v-show="file.not_evaluated">
          <div class="text-xs">This file was not evaluated.</div>
        </div>
      </div>
    </div>
  </div>
  <div v-if="!filteredChunkedFiles.length" class="ml-2 mt-6 text-base">
    <div v-if="loadingMoreFiles" class="flex items-center gap-3">
      <TWESpinner :size="4" />
      <div>Wait until all files are loaded or</div>
    </div>
    <div class="mt-2 flex gap-2">
      <ChevronDoubleLeftIcon class="inline w-5" />
      Select a file to view from the list
    </div>
  </div>
</template>
