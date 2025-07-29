<script setup lang="ts">
import AISummary from "@/aicm/components/common/AISummary.vue";
import AlertMessage from "@/aicm/components/common/AlertMessage.vue";
import Teleports from "@/aicm/components/common/Teleports.vue";
import TWESpinner from "@/aicm/components/common/TWESpinner.vue";
import FileViewer from "@/aicm/components/FileViewer/FileViewer.vue";
import {
  getPullRequestComposition,
  getRepositoryFileDetails,
  getRepositoryFiles,
  getRepositoryFilesNextPage,
} from "@/aicm/helpers/api";
import type { RepositoryFile, RepositoryFileChunk, RepositoryPullRequest } from "@/aicm/helpers/api.d";
import { useRepositoryFilesStore } from "@/aicm/stores/repositoryFiles";
import * as Sentry from "@sentry/vue";
import type { Ref } from "vue";
import { onMounted, ref } from "vue";

// other ways of defining props does not work with the django plugin, default is provided for typescript checker
const props = defineProps({
  aiComposition: { type: String, default: "[]" },
  codeGenerationLabels: { type: String, default: "" },
  notEvaluatedFiles: { type: String, default: "[]" },
  pullRequest: { type: String, default: "{}" },
  repository: { type: String, default: "" },
});

let loading: Ref<boolean> = ref(true);
let loadingComposition: Ref<boolean> = ref(false);
let loadingMoreFiles: Ref<boolean> = ref(false);
let files: Ref<RepositoryFile[]> = ref([]);
let chunkLoading: Ref<boolean> = ref(false);
const errorText = ref("");
const repositoryFilesStore = useRepositoryFilesStore();

const aiComposition: Ref<any> = ref(JSON.parse(props.aiComposition)); // TODO: add type for aiComposition
const notEvaluatedFiles: Ref<string[]> = ref(JSON.parse(props.notEvaluatedFiles));
const pullRequest: Ref<RepositoryPullRequest> = ref(JSON.parse(props.pullRequest));

const loadFiles = async () => {
  const repositoryId = pullRequest.value.repository.public_id;
  const commitSha = pullRequest.value.head_commit_sha;
  try {
    errorText.value = "";
    const response = await getRepositoryFiles(repositoryId, commitSha);
    const repositoryFiles = response.results;
    repositoryFilesStore.addRepositoryFiles(repositoryId, commitSha, repositoryFiles);
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
  const repositoryId = pullRequest.value.repository.public_id;
  const commitSha = pullRequest.value.head_commit_sha;
  loadingMoreFiles.value = true;

  while (nextUrl) {
    let response = await getRepositoryFilesNextPage(nextUrl);
    let repositoryFiles = response.results;
    repositoryFilesStore.addRepositoryFiles(repositoryId, commitSha, repositoryFiles);
    files.value = [...files.value, ...repositoryFiles];
    nextUrl = response.next;
  }

  loadingMoreFiles.value = false;
};

const fetchFile = async (file: RepositoryFile, forced = false) => {
  if (!file?.not_evaluated && (forced || !file.chunks_code_loaded)) {
    if (!forced) chunkLoading.value = true;
    const repositoryId = pullRequest.value.repository.public_id;
    const commitSha = pullRequest.value.head_commit_sha;
    try {
      errorText.value = "";
      const fileDetail = await getRepositoryFileDetails(repositoryId, commitSha, file.public_id);
      fileDetail.chunks_code_loaded = true;
      repositoryFilesStore.updateRepositoryFile(repositoryId, commitSha, fileDetail);
    } catch (error) {
      Sentry.captureException(error);
      errorText.value = "An Error has occurred. Please refresh the page or try again later.";
    } finally {
      chunkLoading.value = false;
    }
  }
};

const refreshComposition = (polling: boolean = false) => {
  // avoid multiple requests
  if (loadingComposition.value && !polling) {
    return;
  }

  const repository = pullRequest.value.repository;

  loadingComposition.value = true;
  getPullRequestComposition(repository.public_id, pullRequest.value.pr_number).then((result) => {
    aiComposition.value = result.ai_composition;

    // PR composition is updated in the background, so we'll keep requesting until it's updated
    // TODO: this is an error-prone approach.
    //       Because many users can be attesting at the same time, we should either
    //       implement a websocket or poll continuously.
    if (result.needs_composition_recalculation) {
      setTimeout(() => refreshComposition(true), 5000);
    } else {
      loadingComposition.value = false;
    }
  });
};

const updateData = ({ file, chunk }: { file: RepositoryFile; chunk: RepositoryFileChunk }) => {
  repositoryFilesStore.clearChunkAffectedFiles(chunk.code_hash, file);
  fetchFile(file, true);
  refreshComposition();
};

const updateAttestedAll = ({ file, chunks }: { file: RepositoryFile; chunks: RepositoryFileChunk[] }) => {
  chunks.forEach((chunk) => {
    repositoryFilesStore.clearChunkAffectedFiles(chunk.code_hash, file);
  });
  fetchFile(file, true);
  refreshComposition();
};

onMounted(() => {
  if (pullRequest.value?.repository) loadFiles();

  if (pullRequest.value.needs_composition_recalculation) {
    refreshComposition();
  }
});
</script>

<template>
  <main class="-mb-14">
    <div v-if="pullRequest?.repository">
      <div class="relative">
        <AISummary
          :aiComposition="aiComposition"
          :isPullRequest="true"
          :loading="loadingComposition"
          :numAnalyzedFiles="pullRequest.analysis_num_files"
          :numNotEvaluatedFiles="pullRequest.not_evaluated_num_files"
        />
      </div>

      <AlertMessage dismissable warning class="mt-10">
        GenAI composition is automatically detected, and it's NOT 100% accurate. Please use the attestation buttons
        below to fix any errors. Thank you!
      </AlertMessage>

      <div v-show="loading" class="mt-10 text-center">
        <TWESpinner />
      </div>
      <div v-show="!loading">
        <div v-show="files.length" class="mt-10">
          <FileViewer
            :codeGenerationLabels
            :repositoryFullName="pullRequest.repository.full_name"
            :repositoryId="pullRequest.repository.public_id"
            :files
            :chunkLoading
            :errorText
            :expandAll="true"
            :loading-more-files="loadingMoreFiles"
            @attested="updateData"
            @attested-all="updateAttestedAll($event)"
            @selectFile="fetchFile($event)"
          />
        </div>

        <div v-if="notEvaluatedFiles.length">
          <h3 class="my-4 mt-10 text-lg font-semibold md:text-xl">
            Not evaluated files ({{ notEvaluatedFiles.length }})
          </h3>
          <ul class="ml-5 mt-5 list-disc">
            <li v-for="filePath in notEvaluatedFiles" :key="filePath" class="text-sm">{{ filePath }}</li>
          </ul>
        </div>

        <div v-else-if="!files.length" class="mt-10">We found no supported files in this Pull Request.</div>
      </div>
    </div>
    <Teleports />
  </main>
</template>
