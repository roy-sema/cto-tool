<script setup lang="ts">
import AzureDevOpsLogo from "@/compass/assets/icons/integrations/azure-devops-logo.svg?component";
import BitBucketLogo from "@/compass/assets/icons/integrations/bitbucket-logo.svg?component";
import GitHubLogoIcon from "@/compass/assets/icons/integrations/github-logo.svg?component";
import SemaLogoIcon from "@/compass/assets/icons/sema-logo.svg?component";
import { assignGitSetupToColleague, getConnectGitProviderData, getOrganizationUsers } from "@/compass/helpers/api";
import { ArrowRightIcon, ArrowsRightLeftIcon, CheckIcon } from "@heroicons/vue/24/outline";
import * as Sentry from "@sentry/vue";
import type { AutoCompleteCompleteEvent } from "primevue/autocomplete";
import { useToast } from "primevue/usetoast";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const toast = useToast();

const loadingConnectData = ref<boolean>(true);
const loadingOrganizationUserEmails = ref<boolean>(true);
const connectAzureDevOpsURL = ref<string>();
const connectBitBucketURL = ref<string>();
const connectGitHubURL = ref<string>();
const isConnectedAzureDevOps = ref<boolean>(false);
const isConnectedBitBucket = ref<boolean>(false);
const isConnectedGitHub = ref<boolean>(false);
const modalVisible = ref<boolean>(false);
const organizationEmails = ref<string[]>([]);
const filteredEmails = ref<string[]>([]);
const selectedEmail = ref<string>();

const gitProviders = computed(() => [
  {
    name: "GitHub",
    icon: GitHubLogoIcon,
    isConnected: isConnectedGitHub.value,
    url: connectGitHubURL.value,
    manual: false,
  },
  {
    name: "Azure DevOps",
    icon: AzureDevOpsLogo,
    isConnected: isConnectedAzureDevOps.value,
    url: connectAzureDevOpsURL.value,
    manual: true,
  },
  {
    name: "BitBucket",
    icon: BitBucketLogo,
    isConnected: isConnectedBitBucket.value,
    url: connectBitBucketURL.value,
    manual: false,
  },
]);

// This is faster than iterating over the gitProviders computed property
const isConnected = computed(
  () => isConnectedGitHub.value || isConnectedAzureDevOps.value || isConnectedBitBucket.value,
);

const loadConnectGitProviderData = async () => {
  try {
    loadingConnectData.value = true;
    const response = await getConnectGitProviderData();

    connectAzureDevOpsURL.value = response.azure_devops.url;
    connectBitBucketURL.value = response.bitbucket.url;
    connectGitHubURL.value = response.github.url;

    isConnectedAzureDevOps.value = response.azure_devops.is_connected;
    isConnectedBitBucket.value = response.bitbucket.is_connected;
    isConnectedGitHub.value = response.github.is_connected;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loadingConnectData.value = false;
  }
};

const loadOrganizationUserEmails = async () => {
  try {
    loadingOrganizationUserEmails.value = true;
    let response = await getOrganizationUsers();
    let emails = [];
    emails.push(...response.users.map((user) => user.email));
    while (response.next_page) {
      response = await getOrganizationUsers(response.next_page);
      emails.push(...response.users.map((user) => user.email));
    }
    organizationEmails.value = emails;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loadingOrganizationUserEmails.value = false;
  }
};

onMounted(() => {
  loadConnectGitProviderData();
  loadOrganizationUserEmails();
});

function searchEmails(event: AutoCompleteCompleteEvent) {
  const lowercaseQuery = event.query.toLowerCase();
  filteredEmails.value = organizationEmails.value.filter((email) => email.toLowerCase().includes(lowercaseQuery));
}

function displayError(message: string) {
  toast.add({
    severity: "error",
    summary: "Error",
    detail: message,
  });
}

async function onSubmitAssignGitSetup() {
  const email = selectedEmail.value;
  if (!email) {
    displayError("Please select an email");
    return;
  }

  try {
    await assignGitSetupToColleague(email);

    toast.add({
      severity: "success",
      summary: "Email sent",
      detail: `We sent an email to ${selectedEmail.value}`,
      life: 10000,
    });
  } catch (error) {
    Sentry.captureException(error);
    displayError(`Error sending the email to ${selectedEmail.value}. Please try again.`);
  } finally {
    modalVisible.value = false;
  }
}
</script>

<template>
  <Toast />

  <Dialog v-model:visible="modalVisible" modal header="Assign setup to colleague" class="lg:w-1/3">
    <p class="mb-5">We'll send an email to your colleague asking them to do the Version Control System setup.</p>

    <label for="colleagueEmail">Email:</label>
    <div>
      <AutoComplete
        id="colleagueEmail"
        v-model="selectedEmail"
        :suggestions="filteredEmails"
        forceSelection
        inputClass="w-full"
        class="w-full"
        @complete="searchEmails"
      />
    </div>

    <div class="mt-3 text-sm">
      Can't find your colleague?
      <Button
        type="button"
        label="Invite member"
        as="a"
        href="/settings/members/"
        target="_blank"
        size="small"
        link
        class="!px-0"
      />
    </div>

    <div class="mt-5 flex justify-center">
      <Button type="submit" label="Send" class="w-40" :disabled="!selectedEmail" @click="onSubmitAssignGitSetup" />
    </div>
  </Dialog>

  <div class="centered-wrapper px-5 py-10 pb-20">
    <ProgressSpinner v-if="loadingConnectData" class="size-2" />
    <div v-else>
      <p class="text-center">Connect your GitHub, Azure DevOps or BitBucket account to analyze your code.</p>

      <div class="mt-5 flex flex-col gap-5 xl:flex-row">
        <Card v-for="gitProvider in gitProviders" class="mx-auto w-full sm:w-80">
          <template #content>
            <div class="flex items-center justify-center gap-2">
              <SemaLogoIcon class="size-8 dark:invert" />
              <ArrowsRightLeftIcon class="size-4 opacity-80" />
              <component :is="gitProvider.icon" class="size-8" />
            </div>
            <div class="mt-4 text-center text-2xl font-semibold">Connect {{ gitProvider.name }}</div>
            <Divider />
            <template v-if="!gitProvider.isConnected">
              <Button
                as="a"
                :href="gitProvider.url"
                :label="gitProvider.isConnected ? 'Edit connection' : 'Connect'"
                :severity="gitProvider.isConnected ? 'secondary' : 'contrast'"
                class="w-full"
              />
              <Divider />
              <template v-if="gitProvider.manual">
                <p class="my-2 text-center text-xs text-muted-color">
                  Follow the instructions to manually set up the connection.
                </p>
                <p class="my-2 text-center text-xs text-muted-color">
                  Then, configure which repositories you want to analyze.
                </p>
              </template>
              <template v-else>
                <p class="my-2 text-center text-xs text-muted-color">
                  We will redirect you to {{ gitProvider.name }} to authorize the connection.
                </p>
                <p class="my-2 text-center text-xs text-muted-color">
                  Then, please select the repositories you want to analyze.
                </p>
              </template>
            </template>
            <template v-else>
              <Message severity="success">
                <template #icon>
                  <div class="flex size-6 items-center justify-center rounded-full bg-green-600">
                    <CheckIcon class="size-4 text-white" />
                  </div>
                </template>
                <div>{{ gitProvider.name }} Connected</div>
              </Message>
              <Divider />
              <Button
                as="a"
                :href="gitProvider.url"
                label="Edit connection"
                severity="secondary"
                size="small"
                class="w-full"
              />
            </template>
          </template>
        </Card>
      </div>

      <div v-if="isConnected" class="mt-5 flex justify-center pb-20 xl:pb-0">
        <Button label="Next" iconPos="right" @click="router.push({ name: 'onboarding-connect-jira' })">
          <template #icon>
            <div class="order-1">
              <ArrowRightIcon class="size-4" />
            </div>
          </template>
        </Button>
      </div>
      <template v-else>
        <div class="mx-auto my-5 flex w-80 items-center gap-3 xl:w-2/3">
          <Divider />
          <div class="text-sm text-gray-500">or</div>
          <Divider />
        </div>
        <div class="text-center">
          <Button
            label="Assign setup to colleague"
            :outlined="true"
            severity="secondary"
            class="w-full sm:w-80"
            @click="modalVisible = true"
          />
        </div>
      </template>
    </div>
  </div>
</template>
