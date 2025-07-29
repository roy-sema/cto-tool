<script setup lang="ts">
import ActionPanel from "@/compass/components/sip/ActionPanel.vue";
import LearnMoreDialog from "@/compass/components/sip/LearnMoreDialog.vue";
import PlatformProductPanel from "@/compass/components/sip/PlatformProductPanel.vue";
import SimplePanel from "@/compass/components/sip/SimplePanel.vue";
import { getSIPDashboardData } from "@/compass/helpers/api";
import type { Score } from "@/compass/helpers/api.d";
import * as Sentry from "@sentry/vue";
import {
  Activity,
  ArrowUpRight,
  Brain,
  Clock,
  Database,
  InfoIcon,
  LineChart,
  Mail,
  MessageSquare,
  Ticket,
} from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

interface ScanModule {
  title: string;
  description: string;
  icon: any;
  available: boolean;
  tooltip?: string;
  emailSubject?: string;
}

const loading = ref(false);
const overall_ai = ref();
const score = ref<Score>();
const initiatives = ref();
const modalProduct = ref("");
const modalLearnMoreVisible = ref(false);
const modalRequestVisible = ref(false);

const PlatformRoadmapRadar = computed(() => ({
  title: "Product Roadmap Radar",
  icon: LineChart,
  value: initiatives.value?.count || 0,
  color: "red",
  metric: "Initiatives",
  available: true,
  description: "Track delivery progress and roadmap health",
  to: "product-roadmap-radar",
}));

const PlatformProducts = computed(() => [
  {
    title: "GenAI Radar",
    icon: Brain,
    value: overall_ai.value?.percentage || 0,
    color: overall_ai.value?.color || "",
    metric: "% GenAI Code (2 Weeks)",
    available: true,
    description: "Monitor AI implementation and patterns",
    href: "/genai-radar/",
  },
  {
    title: "Engineering Radar",
    icon: Activity,
    value: score.value?.score || 0,
    color: score.value?.color || "",
    metric: "Codebase Health Score",
    available: true,
    description: "Continuous engineering health monitoring",
    to: "executive-summary",
  },
  {
    title: "Support Radar",
    icon: Ticket,
    value: "XX",
    color: "grey",
    metric: "Support Health Score",
    available: false,
    description: "Track support metrics and customer satisfaction",
  },
]);

const scanModules: ScanModule[] = [
  {
    title: "Codebase Scans",
    description: "Engineering & GenAI assessment reports",
    icon: Activity,
    available: true,
    tooltip: "Not currently available for download. We'll gladly email them to you",
    emailSubject: "Requesting Codebase Scan Reports",
  },
  {
    title: "Product Roadmap Scans",
    description: "Delivery and roadmap analysis reports",
    icon: LineChart,
    available: true,
    tooltip: "Not currently available for download. We'll gladly email them to you",
    emailSubject: "Requesting Product Roadmap Scan Reports",
  },
  {
    title: "Support Scans",
    description: "Support system assessment reports",
    icon: Ticket,
    available: false,
  },
];

const handleLearnMoreClick = (product: string) => {
  modalProduct.value = product;
  modalLearnMoreVisible.value = true;
};

const handleScanClick = (scan: ScanModule) => {
  if (scan.available) {
    modalProduct.value = scan.title;
    modalRequestVisible.value = true;
  }
};

const loadData = async () => {
  try {
    loading.value = true;

    const response = await getSIPDashboardData();
    overall_ai.value = response.overall_ai;
    score.value = response.score;
    initiatives.value = response.initiatives;
  } catch (error) {
    Sentry.captureException(error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="mx-auto min-h-screen max-w-7xl px-4 py-8 sm:px-6 xl:px-2">
    <div class="mb-12">
      <!-- PlatformRoadmapRadar Section -->
      <div class="grid grid-cols-1 gap-6">
        <PlatformProductPanel
          :title="PlatformRoadmapRadar.title"
          :icon="PlatformRoadmapRadar.icon"
          :value="PlatformRoadmapRadar.value"
          :color="PlatformRoadmapRadar.color"
          :metric="PlatformRoadmapRadar.metric"
          :description="PlatformRoadmapRadar.description"
          :to="PlatformRoadmapRadar.to"
          :loading="loading"
        />
      </div>
    </div>

    <div class="mb-12">
      <h2 class="mb-6 text-xl font-semibold">Platform Products</h2>
      <div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        <PlatformProductPanel
          v-for="(module, index) in PlatformProducts"
          :key="index"
          :title="module.title"
          :icon="module.icon"
          :value="module.value"
          :color="module.color"
          :metric="module.metric"
          :description="module.description"
          :comingSoon="!module.available"
          :to="module.to"
          :href="module.href"
          :loading="loading"
        />
      </div>
    </div>

    <!-- Scans Section -->
    <div class="mb-12">
      <h2 class="mb-6 text-xl font-semibold">Point-in-Time Scans</h2>
      <div class="grid grid-cols-1 gap-6 md:grid-cols-4">
        <ActionPanel
          v-for="(module, index) in scanModules"
          :key="index"
          :title="module.title"
          :icon="module.icon"
          :disabled="!module.available"
          :class="{
            'md:col-span-2': !index,
          }"
          @click="() => (module.available ? handleScanClick(module) : handleLearnMoreClick(module.title))"
        >
          <div class="flex min-h-20 flex-col justify-between gap-4">
            <p class="text-sm text-gray-600">{{ module.description }}</p>
            <div v-if="module.available" class="group relative">
              <button class="flex items-center space-x-2 text-sky-600 hover:text-sky-700">
                <span class="text-sm font-medium">Get Reports</span>
                <ArrowUpRight class="size-4" />
              </button>
              <!--
              TODO: use v-tooltip?
              These tooltips look better than v-tooltip.
              This is temporary anyway.
            -->
              <div
                v-if="module.tooltip"
                class="absolute bottom-full left-0 mb-2 w-64 rounded-lg bg-gray-800 p-2 text-xs text-white opacity-0 transition-opacity duration-200 group-hover:opacity-100"
              >
                <div class="flex items-start space-x-2">
                  <InfoIcon class="mt-0.5 size-4 flex-shrink-0" />
                  <span>{{ module.tooltip }}</span>
                </div>
              </div>
            </div>
            <div v-else class="flex items-center space-x-2 text-sky-600">
              <Clock class="size-4" />
              <span class="text-sm font-medium">Coming Soon</span>
            </div>
          </div>
        </ActionPanel>
      </div>
    </div>

    <!-- Data Portal & SIA Section -->
    <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div>
        <h2 class="mb-6 text-xl font-semibold">BI Tool</h2>
        <SimplePanel class="cursor-pointer" @click="handleLearnMoreClick('Results Database/BI Tool')">
          <template #header>
            <div class="mb-4 flex items-center justify-between gap-3">
              <div class="flex items-center space-x-3">
                <div class="rounded-lg bg-sky-50 p-2 dark:bg-slate-700">
                  <Database class="size-6" />
                </div>
                <div>
                  <h3 class="font-semibold">Results Database/BI Tool</h3>
                  <div class="flex items-center space-x-2 text-sky-600">
                    <Clock class="size-4" />
                    <span class="text-sm font-medium">Coming Soon</span>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <p class="mb-4 text-sm text-gray-600">See and analyze all of your results across all products</p>
        </SimplePanel>
      </div>

      <div>
        <h2 class="mb-6 text-xl font-semibold">Agent</h2>
        <SimplePanel class="cursor-pointer" @click="handleLearnMoreClick('Sema Intelligence Agent')">
          <template #header>
            <div class="mb-4 flex items-center justify-between gap-3">
              <div class="flex items-center space-x-3">
                <div class="rounded-lg bg-sky-50 p-2 dark:bg-slate-700">
                  <MessageSquare class="size-6" />
                </div>
                <div>
                  <h3 class="font-semibold">Sema Intelligence Agent</h3>
                  <div class="flex items-center space-x-2 text-sky-600">
                    <Clock class="size-4" />
                    <span class="text-sm font-medium">Coming Soon</span>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <div class="mb-4 rounded-lg bg-gray-50 p-4 dark:bg-slate-800">
            <div class="mb-3 flex items-center gap-3">
              <div
                class="flex size-8 items-center justify-center rounded-full bg-sky-100 text-sm text-sky-500 dark:bg-sky-900"
              >
                You
              </div>
              <div class="text-sm font-medium">What's going on with our new mobile app?</div>
            </div>
            <div class="flex items-start gap-3">
              <div
                class="flex size-8 items-center justify-center rounded-full bg-indigo-100 text-sm text-indigo-500 dark:bg-indigo-900"
              >
                <MessageSquare class="size-4" />
              </div>
              <div class="w-full space-y-2 rounded-lg bg-white p-4 text-sm shadow-sm dark:bg-slate-900">
                <div>• Delivery: <span class="text-gray-500">XX months behind schedule</span></div>
                <div>• Codebase Health Score: <span class="text-gray-500">XX (Advanced)</span></div>
                <div>• GenAI Usage: <span class="text-gray-500">XX%</span></div>
              </div>
            </div>
          </div>
          <InputText placeholder="Ask a follow-up question..." size="small" class="w-full" disabled />
        </SimplePanel>
      </div>
    </div>
  </div>

  <LearnMoreDialog v-model:visible="modalLearnMoreVisible" :product="modalProduct" />

  <Dialog
    v-model:visible="modalRequestVisible"
    modal
    :header="`Request ${modalProduct}`"
    :closable="false"
    class="lg:w-1/3"
  >
    <p class="mb-4 text-gray-600">We'll email your reports to you. Please contact us to proceed with your request.</p>

    <div class="mb-4 flex items-center space-x-2">
      <Mail class="size-5 text-gray-400" />
      <span class="text-sm text-gray-500">info@semasoftware.com</span>
    </div>

    <div class="flex justify-end gap-2">
      <Button label="Close" severity="secondary" text @click="modalRequestVisible = false" />
      <Button as="a" :href="`/contact?message=Request ${modalProduct}`" label="Contact Us" />
    </div>
  </Dialog>
</template>
