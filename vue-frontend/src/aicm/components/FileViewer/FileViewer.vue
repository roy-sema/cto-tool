<script setup lang="ts">
import FileDetail from "@/aicm/components/FileViewer/FileDetail.vue";
import FileTree from "@/aicm/components/FileViewer/FilesTree.vue";
import FileTopBar from "@/aicm/components/FileViewer/FileTopBar.vue";
import type { RepositoryFile, RepositoryFileChunk } from "@/aicm/helpers/api.d";
import type { PropType, Ref } from "vue";
import { computed, ref } from "vue";
import VueResizable from "vue-resizable";

const props = defineProps({
  codeGenerationLabels: { type: String, default: "" },
  repositoryFullName: { type: String, default: "" },
  repositoryId: { type: String, default: "" },
  files: { type: Array as PropType<RepositoryFile[]>, default: () => [] },
  chunkLoading: { type: Boolean, default: false },
  errorText: { type: String, default: "" },
  expandAll: { type: Boolean, default: false },
  loadingMoreFiles: { type: Boolean, default: false },
});
const emit = defineEmits(["attested", "attestedAll", "selectFile"]);

const codeGenerationLabels: Ref<{ [key: string]: string }> = ref(JSON.parse(props.codeGenerationLabels));
const filters: Ref<string[]> = ref(Object.keys(codeGenerationLabels.value));
const filteredChunkedFiles: Ref<RepositoryFile[]> = ref([]);
const showBlame: Ref<boolean> = ref(true);

const attestationLabels = computed(() => {
  // remove not_evaluated key
  const { not_evaluated, ...filteredLabels } = codeGenerationLabels.value;
  return filteredLabels;
});

const selectedFile = ref<string>("");
const selectFile = (file: RepositoryFile) => {
  if (file) selectedFile.value = file.public_id;
  else selectedFile.value = "all";
  emit("selectFile", file);
};

const selectedFiles = computed(() => {
  return props.files.filter((file) => file.public_id === selectedFile.value);
});

const selectedChunks: Ref<RepositoryFileChunk[]> = computed(() => {
  return filteredChunkedFiles.value.length > 0 ? filteredChunkedFiles.value[0].chunks : [];
});
</script>

<template>
  <div
    v-if="errorText"
    class="relative mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-sm text-red-700"
    role="alert"
  >
    {{ errorText }}
  </div>
  <div class="flex flex-row gap-4">
    <VueResizable
      class="file-viewer !h-auto whitespace-nowrap border-r border-gray-200 dark:border-slate-600"
      :active="['r']"
      :width="208"
      :minWidth="208"
      :maxWidth="500"
    >
      <div class="sticky top-0 mb-3 h-auto max-h-screen w-full overflow-y-auto overflow-x-hidden pb-10 pr-2 pt-5">
        <FileTree
          :files
          :expandAll="props.expandAll"
          :loadingMoreFiles="props.loadingMoreFiles"
          :selectedFiles
          :selected-filters="filters"
          @selectFile="selectFile"
        />
      </div>
    </VueResizable>
    <div class="flex-1">
      <FileTopBar
        :repositoryId="props.repositoryId"
        :selectedFiles
        :repositoryFullName
        :codeGenerationLabels="codeGenerationLabels"
        :selectedChunks="selectedChunks"
        @filter-changed="filters = $event"
        @blame-changed="showBlame = $event"
        @attested-all="emit('attestedAll', { file: filteredChunkedFiles[0], chunks: selectedChunks, ...$event })"
      />
      <FileDetail
        v-if="files.length"
        :files="selectedFiles"
        :repositoryId="props.repositoryId"
        :loadingMoreFiles="props.loadingMoreFiles"
        :selected-filters="filters"
        :codeGenerationLabels
        :attestationLabels
        :chunkLoading
        :showBlame
        @attested="emit('attested', $event)"
        @filteredChunkedFiles="filteredChunkedFiles = $event"
      />
      <div v-else>There are no analyzed files.</div>
    </div>
  </div>
</template>

<style scoped>
.file-viewer {
  --fixed-topbar-height: 67px;
  --footer-height: 53px;
  min-height: calc(100vh - var(--fixed-topbar-height) - var(--footer-height));
}
:deep(.resizable-component > .resizable-r) {
  @apply m-0.5 my-0 !w-1.5 !cursor-col-resize;
}
:deep(.resizable-component > .resizable-r:hover) {
  @apply z-0 bg-blue;
}
</style>
