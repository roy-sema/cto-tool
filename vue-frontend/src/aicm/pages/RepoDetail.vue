<script setup lang="ts">
import Teleports from "@/aicm/components/common/Teleports.vue";
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import FileViewer from "@/aicm/components/FileViewer/FileViewer.vue";
import { getRepositoryFileDetails, getRepositoryFiles, getRepositoryFilesNextPage } from "@/aicm/helpers/api";
import type { RepositoryFile, RepositoryFileChunk } from "@/aicm/helpers/api.d";
import { useRepositoryFilesStore } from "@/aicm/stores/repositoryFiles";
import * as Sentry from "@sentry/vue";
import type { Ref } from "vue";
import { ref } from "vue";

// other ways of defining props does not work with the django plugin, default is provided for typescript checker
const props = defineProps({
  repositoryFullName: { type: String, default: "" },
  repositoryPkEncoded: { type: String, default: "" },
  commitSha: { type: String, default: "" },
  codeGenerationLabels: { type: String, default: "" },
});

let loading: Ref<boolean> = ref(true);
let loadingMoreFiles: Ref<boolean> = ref(false);
let files: Ref<RepositoryFile[]> = ref([]);
let chunkLoading: Ref<boolean> = ref(false);
const errorText = ref("");
const repositoryFilesStore = useRepositoryFilesStore();

const loadFiles = async () => {
  try {
    errorText.value = "";
    const response = await getRepositoryFiles(props.repositoryPkEncoded, props.commitSha);
    const repositoryFiles = response.results;
    repositoryFilesStore.addRepositoryFiles(props.repositoryPkEncoded, props.commitSha, repositoryFiles, true);
    files.value = repositoryFiles;
    if (response.next) {
      loadFilesNextPages(response.next);
    }
  } catch (error) {
    Sentry.captureException(error);
    errorText.value = "An Error has occurred. Please refresh the page or try again later.";
  } finally {
    loading.value = false;
  }
};

const loadFilesNextPages = async (nextUrl: string) => {
  loadingMoreFiles.value = true;

  while (nextUrl) {
    let response = await getRepositoryFilesNextPage(nextUrl);
    let repositoryFiles = response.results;
    repositoryFilesStore.addRepositoryFiles(props.repositoryPkEncoded, props.commitSha, repositoryFiles);
    files.value = [...files.value, ...repositoryFiles];
    nextUrl = response.next;
  }

  loadingMoreFiles.value = false;
};

const fetchFile = async (file: RepositoryFile, forced = false) => {
  if (!file?.not_evaluated && (forced || !file.chunks_code_loaded)) {
    if (!forced) chunkLoading.value = true;
    try {
      errorText.value = "";
      const fileDetail = await getRepositoryFileDetails(props.repositoryPkEncoded, props.commitSha, file.public_id);
      fileDetail.chunks_code_loaded = true;
      repositoryFilesStore.updateRepositoryFile(props.repositoryPkEncoded, props.commitSha, fileDetail);
    } catch (error) {
      Sentry.captureException(error);
      errorText.value = "An Error has occurred. Please refresh the page or try again later.";
    } finally {
      chunkLoading.value = false;
    }
  }
};

const updateData = ({ file, chunk }: { file: RepositoryFile; chunk: RepositoryFileChunk }) => {
  repositoryFilesStore.clearChunkAffectedFiles(chunk.code_hash, file);
  fetchFile(file, true);
};

const updateAttestedAll = ({ file, chunks }: { file: RepositoryFile; chunks: RepositoryFileChunk[] }) => {
  chunks.forEach((chunk) => {
    repositoryFilesStore.clearChunkAffectedFiles(chunk.code_hash, file);
  });
  fetchFile(file, true);
};

loadFiles();
</script>

<template>
  <main class="-mb-20">
    <div v-show="loading" class="mt-16 text-center">
      <TWESpinner />
    </div>
    <div v-show="!loading">
      <FileViewer
        :codeGenerationLabels
        :repositoryFullName
        :repositoryId="props.repositoryPkEncoded"
        :files
        :chunkLoading
        :errorText
        :loading-more-files="loadingMoreFiles"
        @attested="updateData($event)"
        @attested-all="updateAttestedAll($event)"
        @selectFile="fetchFile($event)"
      />
    </div>

    <Teleports />
  </main>
</template>
