<script setup lang="ts">
import type { IntegrationStatusMap } from "@/common/api.d";
import AWSLogoIcon from "@/compass/assets/icons/integrations/aws-logo.svg?component";
import AzureDevOpsLogoIcon from "@/compass/assets/icons/integrations/azure-devops-logo.svg?component";
import BitbucketLogoIcon from "@/compass/assets/icons/integrations/bitbucket-logo.svg?component";
import CodacyLogoIcon from "@/compass/assets/icons/integrations/codacy-logo.svg?component";
import GitHubLogoIcon from "@/compass/assets/icons/integrations/github-logo.svg?component";
import IRadarLogoIcon from "@/compass/assets/icons/integrations/iradar-logo.svg?component";
import JenkinsLogoIcon from "@/compass/assets/icons/integrations/jenkins-logo.svg?component";
import JiraLogoIcon from "@/compass/assets/icons/integrations/jira-logo.svg?component";
import QuickbooksLogoIcon from "@/compass/assets/icons/integrations/quickbooks-logo.svg?component";
import SnykLogoIcon from "@/compass/assets/icons/integrations/snyk-logo.svg?component";
import WorkplaceLogoIcon from "@/compass/assets/icons/integrations/workplace-logo.svg?component";
import { XCircleIcon } from "@heroicons/vue/24/outline";
import type { Component } from "vue";
import { computed } from "vue";

const props = defineProps<{
  integrations: IntegrationStatusMap;
}>();

const integrationIconMap: { [key: string]: Component } = {
  aws: AWSLogoIcon,
  azuredevops: AzureDevOpsLogoIcon,
  bitbucket: BitbucketLogoIcon,
  codacy: CodacyLogoIcon,
  github: GitHubLogoIcon,
  iradar: IRadarLogoIcon,
  jenkins: JenkinsLogoIcon,
  jira: JiraLogoIcon,
  quickbooks: QuickbooksLogoIcon,
  snyk: SnykLogoIcon,
  workplace: WorkplaceLogoIcon,
};

const processedIntegrations = computed(() => {
  return Object.entries(props.integrations).map(([key, value]) => ({
    ...value,
    icon: integrationIconMap[key] ?? false,
  }));
});
</script>

<template>
  <div class="integrations flex gap-1">
    <template v-for="integration in processedIntegrations" :key="integration.key">
      <div class="integration flex items-center gap-1">
        <component :is="integration.icon" v-if="integration.icon" class="size-4 dark:text-gray-100" />
        <XCircleIcon v-else class="size-4 dark:text-gray-100" />
        <span class="text-xs">{{ integration.display_name }}</span>
        <span v-if="!integration.status" class="text-xs font-bold text-red-500">✕</span>
      </div>
    </template>
  </div>
</template>
