<script setup lang="ts">
import { uploadDocuments } from "@/compass/helpers/api";
import {
  ArrowRightIcon,
  ArrowUpOnSquareIcon,
  CheckCircleIcon,
  DocumentIcon,
  XMarkIcon,
} from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const props = withDefaults(
  defineProps<{
    isOnboarding?: boolean;
  }>(),
  {
    isOnboarding: true,
  },
);

const router = useRouter();

const MAX_FILE_SIZE = 1024 * 1024 * 50; // 50MB
const MAX_FILE_NAME_LENGTH = 25;

const uploader = ref();
const chooseFile = ref();
const uploadFiles = ref();
const validationSuccesses = ref<string[]>([]);
const validationErrors = ref<string[]>([]);
const uploadingFiles = ref(false);

onMounted(() => {
  chooseFile.value = uploader.value.choose;
  uploadFiles.value = uploader.value.upload;
});

async function onSubmitUploadFiles(event: any) {
  uploadingFiles.value = true;
  validationSuccesses.value = [];
  validationErrors.value = [];

  try {
    const response = await uploadDocuments(event.files);
    validationSuccesses.value = response.successes || [];

    if (response.errors) {
      validationErrors.value = response.errors;
    }
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    uploadingFiles.value = false;
  }
}

function formatFileName(fileName: string) {
  const extensionIndex = fileName.lastIndexOf(".");
  const extension = extensionIndex !== -1 ? fileName.slice(extensionIndex) : "";
  const nameWithoutExtension = extensionIndex !== -1 ? fileName.slice(0, extensionIndex) : fileName;
  if (nameWithoutExtension.length > MAX_FILE_NAME_LENGTH) {
    return `${nameWithoutExtension.slice(0, MAX_FILE_NAME_LENGTH)}...${extension}`;
  }
  return fileName;
}

function formatFileSize(fileSize: number) {
  return `${Math.ceil(fileSize / 1024)}KB`;
}
</script>

<template>
  <div class="centered-wrapper -mt-5">
    <ProgressSpinner v-if="uploadingFiles" class="size-2" />
    <div class="w-[500px]" :class="{ hidden: uploadingFiles }">
      <Card class="mx-auto">
        <template #content>
          <FileUpload
            ref="uploader"
            name="compass-documents[]"
            :multiple="true"
            class="w-900"
            :customUpload="true"
            @uploader="onSubmitUploadFiles"
          >
            <template #header>
              <div class="w-full">
                <div class="mb-2 text-center text-2xl font-semibold">Upload Documents</div>
                <div class="mb-2 text-center text-sm text-gray-600">
                  Files uploaded are limited to {{ MAX_FILE_SIZE / 1024 / 1024 }}MB
                </div>
              </div>
            </template>
            <template #content="{ files, removeFileCallback }">
              <div v-if="files.length" class="h-60 rounded-md border-2 border-dashed border-gray-500 p-4 text-center">
                <ArrowUpOnSquareIcon class="ml-auto mr-auto mt-10 size-8" />
                <div class="mt-5">
                  <p>
                    Drag-and-drop file, or
                    <span class="cursor-pointer text-blue" @click="chooseFile">browse computer</span>
                  </p>
                </div>
              </div>
              <div v-if="files.length > 0">
                <div class="flex max-h-[160px] flex-wrap gap-4 overflow-y-auto">
                  <div
                    v-for="(file, index) in files"
                    :key="file.name + file.type + file.size"
                    class="flex w-full flex-shrink-0 flex-col rounded-md border border-gray-500 border-surface p-1"
                  >
                    <div class="flex">
                      <DocumentIcon class="size-8" />
                      <div class="ml-2 mt-1">
                        {{ formatFileName(file.name)
                        }}<span class="ml-2 text-gray-600">{{ formatFileSize(file.size) }}</span>
                      </div>
                      <XMarkIcon
                        class="ml-auto size-8 cursor-pointer text-red-600"
                        @click="removeFileCallback(index)"
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div class="w-full">
                <div v-if="validationSuccesses.length > 0" class="flex justify-center">
                  <CheckCircleIcon class="size-8 text-green-700" />
                  <p class="ml-2 mt-1">{{ validationSuccesses.length }} files successfully upload</p>
                </div>
                <div v-if="validationErrors.length > 0">
                  <div class="mt-5 flex justify-center">
                    <XMarkIcon class="size-8 text-red-600" />
                    <p class="ml-2 mt-1">There was a problem uploading these files:</p>
                  </div>
                  <p v-for="(error, index) in validationErrors" :key="index" class="m-2 text-center">
                    {{ error }}
                  </p>
                </div>
              </div>
              <Button v-if="files.length" label="Upload Files" iconPos="right" @click="uploadFiles">
                <template #icon>
                  <div class="order-1">
                    <ArrowUpOnSquareIcon class="size-5" />
                  </div>
                </template>
              </Button>
            </template>
            <template #empty>
              <div class="w-600 h-60 rounded-md border-2 border-dashed border-gray-500 p-4 text-center">
                <ArrowUpOnSquareIcon class="ml-auto mr-auto mt-10 size-8" />
                <div class="mt-5">
                  <p>
                    Drag-and-drop file, or
                    <span class="cursor-pointer text-blue" @click="chooseFile">browse computer</span>
                  </p>
                </div>
              </div>
            </template>
          </FileUpload>
        </template>
      </Card>
      <div v-if="props.isOnboarding" class="mt-5 flex justify-center">
        <Button label="Next" iconPos="right" @click="router.push({ name: 'onboarding-insights-notifications' })">
          <template #icon>
            <div class="order-1">
              <ArrowRightIcon class="size-4" />
            </div>
          </template>
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.p-fileupload-advanced {
  @apply !border-none;
}
</style>
