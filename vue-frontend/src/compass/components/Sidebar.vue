<script setup lang="ts">
import DonutChartIcon from "@/compass/assets/icons/donut-chart.svg?component";
import HeartbeatIcon from "@/compass/assets/icons/heartbeat.svg?component";
import HomeIcon from "@/compass/assets/icons/home.svg?component";
import TargetIcon from "@/compass/assets/icons/target.svg?component";
import OnboardingStepper from "@/compass/components/OnboardingStepper.vue";
import UserDropdown from "@/compass/components/UserDropdown.vue";
import { useSidebarStore } from "@/compass/stores/sidebar";
import {
  ArrowUpTrayIcon,
  ClipboardDocumentListIcon,
  CubeIcon,
  EnvelopeIcon,
  LightBulbIcon,
  NewspaperIcon,
  PresentationChartBarIcon,
  ShieldCheckIcon,
  XMarkIcon,
} from "@heroicons/vue/24/outline";
import { computed, type FunctionalComponent, type SVGAttributes } from "vue";
import { useRoute } from "vue-router";

interface SidebarSection {
  icon: FunctionalComponent<SVGAttributes, {}, any, {}>;
  iconClass: string;
  name: string;
  route: string;
  beta?: boolean;
}

const route = useRoute();
const sidebarStore = useSidebarStore();

const isOnboarding = computed(() => route.name && (route.name as string).startsWith("onboarding-"));

const productRoadmapRadarSections: SidebarSection[] = [
  {
    icon: HomeIcon,
    iconClass: "size-5",
    name: "Home",
    route: "product-roadmap-radar",
  },
  {
    icon: EnvelopeIcon,
    iconClass: "size-5",
    name: "Daily Message",
    route: "daily-message",
  },
  {
    icon: PresentationChartBarIcon,
    iconClass: "size-6",
    name: "Development Activity",
    route: "development-activity",
  },
  {
    icon: TargetIcon,
    iconClass: "size-5",
    name: "Product Roadmap",
    route: "roadmap",
  },
  {
    icon: ClipboardDocumentListIcon,
    iconClass: "size-5",
    name: "Ticket Completeness",
    route: "ticket-completeness",
  },
  {
    icon: NewspaperIcon,
    iconClass: "size-5",
    name: "Anomaly Insights",
    route: "anomaly-insights",
  },
  {
    icon: LightBulbIcon,
    iconClass: "size-5",
    name: "Raw Results",
    route: "raw-contextualization-data",
    beta: true,
  },
  {
    icon: ArrowUpTrayIcon,
    iconClass: "size-5",
    name: "File Uploads",
    route: "file-uploads",
  },
];

const engineeringRadarSections: SidebarSection[] = [
  {
    icon: PresentationChartBarIcon,
    iconClass: "size-6",
    name: "Executive Summary",
    route: "executive-summary",
  },
  {
    icon: CubeIcon,
    iconClass: "size-6",
    name: "Product Detail",
    route: "product-detail",
  },
  {
    icon: ShieldCheckIcon,
    iconClass: "size-6",
    name: "Compliance Detail",
    route: "compliance-detail",
  },
];

const comingSoonSections: SidebarSection[] = [
  {
    icon: HomeIcon,
    iconClass: "size-5",
    name: "Dashboard",
    route: "dashboard",
  },
  // TODO: uncomment when implemented
  // {
  //   icon: ShieldCheckIcon,
  //   iconClass: "size-6",
  //   name: "Policy Compliance",
  //   route: "compliance",
  // },
  {
    icon: HeartbeatIcon,
    iconClass: "size-6",
    name: "Team Health",
    route: "team",
  },
  {
    icon: DonutChartIcon,
    iconClass: "size-5",
    name: "Budget Performance",
    route: "budget",
  },
];

const sections = computed(() => {
  if (route.path.startsWith("/product-roadmap-radar/")) {
    return productRoadmapRadarSections;
  }

  if (route.path.startsWith("/engineering-radar/")) {
    return engineeringRadarSections;
  }

  if (route.path.startsWith("/coming-soon/")) {
    return comingSoonSections;
  }

  return [];
});
</script>

<template>
  <div
    class="relative flex h-full w-full flex-col justify-between border-r dark:border-slate-600 dark:bg-slate-900"
    :class="isOnboarding ? 'lg:w-64' : 'lg:w-60'"
  >
    <div>
      <div class="absolute right-5 top-5 lg:hidden">
        <Button severity="secondary" size="small" text @click="sidebarStore.collapseSidebar">
          <template #icon>
            <XMarkIcon class="size-6" />
          </template>
        </Button>
      </div>

      <div class="mx-4 mt-5 lg:hidden">
        <UserDropdown />
      </div>
    </div>

    <div v-if="isOnboarding" class="-mt-20 overflow-y-auto overflow-x-hidden px-4 pb-5">
      <OnboardingStepper />
    </div>
    <div v-else class="-mt-20 overflow-y-auto overflow-x-hidden">
      <div v-for="section in sections" :key="section.route" class="mt-2 flex flex-col gap-2">
        <router-link
          :to="{ name: section.route }"
          class="relative flex items-center gap-4 p-4 text-sm text-gray-700 transition-colors hover:bg-blue hover:text-white dark:text-gray-300"
          :class="{ 'bg-cyan-50 dark:bg-slate-600': section.route === route.name }"
          @click="sidebarStore.collapseSidebar"
        >
          <!-- NOTE: these icons are not exactly the same size -->
          <div class="flex size-6 items-center justify-center">
            <component :is="section.icon" :class="section.iconClass" />
          </div>
          <span>{{ section.name }} <sup v-if="section.beta">Beta</sup></span>
        </router-link>
      </div>
    </div>

    <!-- empty element so flex positions menu in the middle -->
    <div />
  </div>
</template>
