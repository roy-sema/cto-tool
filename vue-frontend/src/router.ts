import { createRouter, createWebHistory } from "vue-router";

import AnomalyInsights from "@/compass/pages/AnomalyInsights.vue";
import DailyMessage from "@/compass/pages/DailyMessage.vue";
import TicketCompleteness from "@/compass/pages/TicketCompleteness.vue";
import UploadDocumentsPage from "@/compass/pages/UploadDocumentsPage.vue";
import UploadDocumentsSettings from "@/compass/pages/UploadDocumentsSettings.vue";
import AICodeMonitorDashboard from "./aicm/pages/AICodeMonitorDashboard.vue";
import DeveloperGroupDashboard from "./aicm/pages/DeveloperGroupDashboard.vue";
import InsightsNotificationsSettings from "./aicm/pages/InsightsNotificationsSettings.vue";
import PullRequestScan from "./aicm/pages/PullRequestScan.vue";
import RepoDetail from "./aicm/pages/RepoDetail.vue";
import RepositoryGroupDashboard from "./aicm/pages/RepositoryGroupDashboard.vue";
import VueCompatibility from "./aicm/pages/VueCompatibility.vue";

import EmptyLayout from "./compass/layouts/EmptyLayout.vue";
import SidebarLayout from "./compass/layouts/SidebarLayout.vue";
import Budget from "./compass/pages/Budget.vue";
import Compliance from "./compass/pages/Compliance.vue";
import ComplianceDetail from "./compass/pages/ComplianceDetail.vue";
import ConnectJira from "./compass/pages/ConnectJira.vue";
import Dashboard from "./compass/pages/Dashboard.vue";
import DevelopmentActivity from "./compass/pages/DevelopmentActivity.vue";
import ExecutiveSummary from "./compass/pages/ExecutiveSummary.vue";
import OnboardingConnectJira from "./compass/pages/onboarding/ConnectJira.vue";
import OnboardingConnectVCS from "./compass/pages/onboarding/ConnectVCS.vue";
import InsightsNotificationsOnboarding from "./compass/pages/onboarding/InsightsNotificationsOnboarding.vue";
import Welcome from "./compass/pages/onboarding/Welcome.vue";
import ProductDetail from "./compass/pages/ProductDetail.vue";
import RawContextualizationData from "./compass/pages/RawContextualizationData.vue";
import Roadmap from "./compass/pages/Roadmap.vue";
import SIPDashboard from "./compass/pages/sip/Dashboard.vue";
import ProductRoadmapRadar from "./compass/pages/sip/ProductRoadmapRadar.vue";
import Team from "./compass/pages/Team.vue";
import UserProfile from "./compass/pages/UserProfile.vue";

const onboardingRoutes = [
  {
    path: "connect-vcs",
    name: "onboarding-connect-vcs",
    component: OnboardingConnectVCS,
  },
  {
    path: "connect-jira",
    name: "onboarding-connect-jira",
    component: OnboardingConnectJira,
  },
  {
    path: "product-roadmap",
    name: "onboarding-product-roadmap",
    component: Roadmap,
  },
  {
    path: "insights-notifications",
    name: "onboarding-insights-notifications",
    component: InsightsNotificationsOnboarding,
  },
];

export const routes = [
  { path: "/profile", name: "profile", component: UserProfile },
  { path: "/onboarding/welcome", name: "welcome", component: Welcome },
  { path: "/genai-radar/repository-groups/", component: RepositoryGroupDashboard },
  { path: "/genai-radar/developer-groups/", component: DeveloperGroupDashboard },
  { path: "/genai-radar/repositories/:path?", component: RepoDetail },
  { path: "/genai-radar/pulls/:path?", component: PullRequestScan },
  { path: "/genai-radar/dashboard", component: AICodeMonitorDashboard },
  { path: "/settings/daily-message", component: InsightsNotificationsSettings, meta: { layout: EmptyLayout } },
  { path: "/settings/documents", component: UploadDocumentsSettings, meta: { layout: EmptyLayout } },
  { path: "/settings/connect/jira", component: ConnectJira, meta: { layout: EmptyLayout } },

  {
    path: "/home",
    name: "home",
    component: SIPDashboard,
  },
  {
    path: "/onboarding",
    name: "onboarding",
    redirect: `/onboarding/${onboardingRoutes[0].path}`,
    children: onboardingRoutes,
    meta: { layout: SidebarLayout },
  },
  {
    path: "/engineering-radar",
    redirect: "/engineering-radar/executive-summary",
    meta: { layout: SidebarLayout },
    children: [
      {
        path: "compliance-detail",
        name: "compliance-detail",
        component: ComplianceDetail,
      },
      {
        path: "executive-summary",
        name: "executive-summary",
        component: ExecutiveSummary,
      },
      {
        path: "product-detail",
        name: "product-detail",
        component: ProductDetail,
      },
    ],
  },
  {
    path: "/product-roadmap-radar",
    children: [
      {
        path: "",
        name: "product-roadmap-radar",
        component: ProductRoadmapRadar,
      },
      {
        path: "development-activity",
        name: "development-activity",
        component: DevelopmentActivity,
        meta: { layout: SidebarLayout },
      },
      {
        path: "roadmap",
        name: "roadmap",
        component: Roadmap,
        meta: { layout: SidebarLayout },
      },
      {
        path: "daily-message",
        name: "daily-message",
        component: DailyMessage,
        meta: { layout: SidebarLayout },
      },
      {
        path: "ticket-completeness",
        name: "ticket-completeness",
        component: TicketCompleteness,
        meta: { layout: SidebarLayout },
      },
      {
        path: "anomaly-insights",
        name: "anomaly-insights",
        component: AnomalyInsights,
        meta: { layout: SidebarLayout },
      },
      {
        path: "raw-contextualization-data",
        name: "raw-contextualization-data",
        component: RawContextualizationData,
        meta: { layout: SidebarLayout },
      },
      {
        path: "file-uploads",
        name: "file-uploads",
        component: UploadDocumentsPage,
        meta: { layout: SidebarLayout },
      },
    ],
  },
  {
    path: "/coming-soon",
    redirect: "/coming-soon/dashboard",
    meta: { layout: SidebarLayout },
    children: [
      {
        path: "budget",
        name: "budget",
        component: Budget,
      },
      {
        path: "compliance",
        name: "compliance",
        component: Compliance,
      },
      {
        path: "dashboard",
        name: "dashboard",
        component: Dashboard,
      },
      {
        path: "team",
        name: "team",
        component: Team,
      },
    ],
  },
  { path: "/:path?", component: VueCompatibility, meta: { layout: EmptyLayout } },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    } else {
      return { top: 0, left: 0 };
    }
  },
});
