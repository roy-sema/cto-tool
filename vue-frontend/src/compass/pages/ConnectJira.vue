<script setup lang="ts">
import Teleports from "@/aicm/components/common/Teleports.vue";
import JiraLogoIcon from "@/compass/assets/icons/integrations/jira-logo.svg?component";
import SemaLogoIcon from "@/compass/assets/icons/sema-logo.svg?component";
import { getConnectJiraData, updateJiraProjectSelection } from "@/compass/helpers/api";
import type { JiraProject } from "@/compass/helpers/api.d";
import { ArrowsRightLeftIcon, CheckIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import { useToast } from "primevue/usetoast";
import { nextTick, onMounted, ref } from "vue";

const props = withDefaults(
  defineProps<{
    isOnboarding?: boolean;
  }>(),
  {
    isOnboarding: false,
  },
);

const toast = useToast();
const loadingConnectJiraData = ref<boolean>(true);
const loadingProjectUpdate = ref<boolean>(false);
const connectJiraURL = ref<string>();
const isConnected = ref<boolean>();
const projects = ref<JiraProject[]>();

const loadConnectJiraData = async () => {
  try {
    loadingConnectJiraData.value = true;
    const response = await getConnectJiraData(props.isOnboarding);
    connectJiraURL.value = response.url;
    isConnected.value = response.is_connected;
    projects.value = response.projects;
  } catch (error) {
    Sentry.captureException(error);
    displayError("Failed to load Jira connection data");
  } finally {
    loadingConnectJiraData.value = false;
  }
};

onMounted(async () => {
  loadConnectJiraData();
  // Wait for DOM updates so toast is correctly rendered
  await nextTick();
  const urlParams = new URLSearchParams(window.location.search);
  const status = urlParams.get("status") as "error" | "success";
  const message = urlParams.get("message");
  if (status && message) {
    toast.add({
      severity: status,
      summary: status.toUpperCase(),
      detail: message,
      life: 5000,
    });
  }
});

function displayError(message: string) {
  toast.add({
    severity: "error",
    summary: "Error",
    detail: message,
  });
}

async function toggleProjectSelection(project: JiraProject) {
  try {
    loadingProjectUpdate.value = true;
    const updatedSelection = !project.is_selected;

    await updateJiraProjectSelection(project.public_id, updatedSelection);

    // Update local state after successful API call
    if (projects.value) {
      const projectIndex = projects.value.findIndex((p) => p.public_id === project.public_id);
      if (projectIndex >= 0) {
        projects.value[projectIndex].is_selected = updatedSelection;
      }
    }
  } catch (error) {
    Sentry.captureException(error);
    displayError("Failed to update project selection");
  } finally {
    loadingProjectUpdate.value = false;
  }
}
</script>

<template>
  <div class="sip mt-5">
    <div v-if="loadingConnectJiraData" class="mt-15 flex justify-center">
      <ProgressSpinner class="size-2" />
    </div>
    <div v-else>
      <Card class="mx-auto w-full max-w-3xl px-4 sm:px-6 lg:px-8">
        <template #content>
          <div class="flex items-center justify-center gap-2">
            <SemaLogoIcon class="size-8 dark:invert" />
            <ArrowsRightLeftIcon class="size-4 opacity-80" />
            <JiraLogoIcon class="size-8" />
          </div>
          <div class="mt-4 text-center text-2xl font-semibold">Connect Jira</div>
          <Divider />
          <template v-if="!isConnected">
            <div class="flex justify-center">
              <Button as="a" :href="connectJiraURL" label="Connect" severity="contrast" size="small" />
            </div>
          </template>
          <template v-else>
            <Message severity="success">
              <template #icon>
                <div class="flex size-6 items-center justify-center rounded-full bg-green-600">
                  <CheckIcon class="size-4 text-white" />
                </div>
              </template>
              <div>Jira Connected</div>
            </Message>
            <Divider />
            <div class="flex justify-center">
              <Button as="a" :href="connectJiraURL" label="Edit connection" severity="secondary" size="small" />
            </div>

            <div v-if="projects && projects.length > 0" class="mt-6">
              <h3 class="mb-3 text-lg font-medium">Select Jira Projects</h3>
              <div>
                <div
                  v-for="project in projects"
                  :key="project.public_id"
                  class="mb-2 flex items-center rounded border p-3 dark:border-gray-700"
                >
                  <Checkbox
                    :model-value="project.is_selected"
                    :binary="true"
                    :disabled="loadingProjectUpdate"
                    :inputId="'project-' + project.public_id"
                    @update:model-value="toggleProjectSelection(project)"
                  />
                  <label :for="'project-' + project.public_id" class="ml-2 flex w-full cursor-pointer justify-between">
                    <div>{{ project.name }}</div>
                    <div class="content-center text-xs text-muted-color">{{ project.key }}</div>
                  </label>
                </div>
              </div>
              <a
                v-if="!isOnboarding"
                href="/settings/repository-groups/"
                class="mt-4 flex justify-self-end text-sm text-blue"
              >
                Link a jira project to a repository group
              </a>
            </div>
            <div v-else-if="projects && projects.length === 0" class="mt-6">
              <Message severity="info">
                No Jira projects found. Please make sure your Jira account has projects.
              </Message>
            </div>
          </template>
        </template>
      </Card>
    </div>
    <Teleports v-if="!isOnboarding" />
    <Toast />
  </div>
</template>
