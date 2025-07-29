<script setup lang="ts">
import AWSLogoIcon from "@/compass/assets/icons/integrations/aws-logo.svg?component";
import BackstageLogoIcon from "@/compass/assets/icons/integrations/backstage-logo.svg?component";
import JenkinsCodeSecurityIcon from "@/compass/assets/icons/integrations/jenkins-code-security-logo.svg?component";
import JenkinsIcon from "@/compass/assets/icons/integrations/jenkins-logo.svg?component";
import JenkinsObservabilityIcon from "@/compass/assets/icons/integrations/jenkins-observability-logo.svg?component";
import SonarQubeLogoIcon from "@/compass/assets/icons/integrations/sonarqube-logo.svg?component";
import OnboardingPickWidgetPanel from "@/compass/components/OnboardingPickWidgetPanel.vue";
import { InformationCircleIcon, PlusIcon } from "@heroicons/vue/24/outline";
import { ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();

// TODO: implement integrations selected
const integrationsSelected = ref<number>(0);

function connectJenkinsCICDPipelineMetrics() {
  console.log("implement connect Jenkins CI/CD pipeline metrics");
}

function connectSonarQube() {
  console.log("implement connect SonarQube");
}

function connectJenkinsCodeSecurity() {
  console.log("implement connect Jenkins code security");
}

function connectJenkinsObservability() {
  console.log("implement connect Jenkins observability");
}

function connectAWSCloudInfrastructure() {
  console.log("implement connect AWS cloud infrastructure");
}

function connectBackstage() {
  console.log("implement connect Backstage");
}

function loadMoreIntegrations() {
  console.log("implement load more integrations");
}
</script>

<template>
  <div class="m-4 flex items-center justify-center pl-2 pr-2">
    <div>
      <Card>
        <template #content>
          <div class="text-2xl font-semibold">Connect Your Integrations</div>
          <p class="text-gray-500">
            Connect your tools to enable data collection. Different insights require different integrations.
          </p>
          <div
            class="my-5 flex items-start gap-2 rounded-md border border-cyan-600 bg-cyan-50 px-4 py-3 dark:bg-cyan-950"
          >
            <InformationCircleIcon class="mt-0.5 size-4 shrink-0 text-cyan-600" />
            <div class="text-sm text-cyan-800 dark:text-cyan-600">
              Select at least one integration. More integrations enable richer insights.
            </div>
          </div>
          <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
            <OnboardingPickWidgetPanel
              header="Jenkins"
              subHeader="CI/CD pipeline metrics"
              :availableInsights="[
                'Deployment frequency & success rate',
                'Meantime to recover from failures',
                'Change failure rate trends',
                'Build time and optimization opportunities',
              ]"
              :connectAction="connectJenkinsCICDPipelineMetrics"
              :Logo="JenkinsIcon"
            />
            <OnboardingPickWidgetPanel
              header="SonarQube"
              subHeader="Code quality"
              :availableInsights="[
                'Technical debt and measurement trends',
                'Code coverage percentage tracking',
                'Code duplication detection tracking',
                'Critical code smells identified',
              ]"
              :connectAction="connectSonarQube"
              :Logo="SonarQubeLogoIcon"
            />
            <OnboardingPickWidgetPanel
              header="Jenkins"
              subHeader="Code security"
              :availableInsights="[
                'Security scan results by severity',
                'Time to fix critical vulnerabilities',
                'Security policy compliance rate',
                'Security testing coverage',
              ]"
              :connectAction="connectJenkinsCodeSecurity"
              :Logo="JenkinsCodeSecurityIcon"
            />
            <OnboardingPickWidgetPanel
              header="Jenkins"
              subHeader="Observability"
              :availableInsights="[
                'Service reliability metrics',
                'Infrastructure performance KPIs',
                'Resource utilization patterns',
                'Operational bottlenecks detected',
              ]"
              :connectAction="connectJenkinsObservability"
              :Logo="JenkinsObservabilityIcon"
            />
            <OnboardingPickWidgetPanel
              header="AWS"
              subHeader="Cloud infrastructure"
              :availableInsights="[
                'Cloud resource utilization rates',
                'Cost per service/transaction',
                'Security compliance status',
                'Service uptime percentage',
              ]"
              :connectAction="connectAWSCloudInfrastructure"
              :Logo="AWSLogoIcon"
            />
            <OnboardingPickWidgetPanel
              header="Backstage"
              subHeader="Developer experience"
              :availableInsights="[
                'Developer onboarding velocity',
                'Internal tool adoption rates',
                'Documentation coverage score',
                'Development environment setup time',
              ]"
              :connectAction="connectBackstage"
              :Logo="BackstageLogoIcon"
            />
          </div>
        </template>
      </Card>
      <div class="mt-8 flex flex-col items-center pb-10 sm:flex-row">
        <Button severity="contrast" @click="loadMoreIntegrations">
          <template #default>
            <PlusIcon class="mt-0.5 size-4 shrink-0" />
            <p>Load more integrations</p>
          </template>
        </Button>
        <p class="mt-2 text-gray-500 sm:ml-auto sm:mr-4 sm:mt-0">{{ integrationsSelected }} integrations selected</p>
        <Button
          label="Continue"
          severity="contrast"
          class="mt-2 sm:mt-0"
          @click="router.push({ name: 'onboarding-llm-prompt-widget' })"
        />
      </div>
    </div>
  </div>
</template>
