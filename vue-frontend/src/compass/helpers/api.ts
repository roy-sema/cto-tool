import { BASE_URL, parseApiResponse, postJSON, putJSON, sendMultipartFormData } from "@/common/api";
import type {
  AnomalyInsightsFilters,
  AnomalyInsightsResponse,
  BudgetPerformanceResponse,
  CodebaseComplianceDetailResponse,
  CodebaseExecutiveSummaryResponse,
  CodebaseProductDetailResponse,
  ConnectGitProviderResponse,
  ConnectJiraResponse,
  DailyMessageFilterResponse,
  DailyMessageResponse,
  DashboardResponse,
  InsightsNotifications,
  MessageFilter,
  OrganizationDeveloperGroupsResponse,
  OrganizationRepositoryGroupsResponse,
  OrganizationUsersResponse,
  ProductRoadmapFiltersResponse,
  ProductRoadmapResponse,
  SIPDashboardResponse,
  SIPProductRoadmapRadarResponse,
  TeamHealthResponse,
  TicketCompletenessFilters,
  TicketCompletenessResponse,
  TicketCompletenessStatisticsResponse,
  TicketCompletenessTicketResponse,
  TicketCompletenessTrendChartResponse,
  UploadDocumentsResponse,
} from "@/compass/helpers/api.d";

const BASE_API_URL = `${BASE_URL}/compass/api/v1`;

export async function assignGitSetupToColleague(email: string): Promise<void> {
  const url = `${BASE_API_URL}/onboarding/assign-git-setup-to-colleague/`;
  return await postJSON(url, { email });
}

export async function assignJiraSetupToColleague(email: string): Promise<void> {
  const url = `${BASE_API_URL}/onboarding/assign-jira-setup-to-colleague/`;
  return await postJSON(url, { email });
}

export async function completeOnboarding(): Promise<void> {
  const url = `${BASE_API_URL}/onboarding/complete/`;
  return await postJSON(url, {});
}

export async function getInsightsNotifications(): Promise<InsightsNotifications> {
  const url = `${BASE_API_URL}/onboarding/insights-notifications/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function setInsightsNotifications(
  anomaly_insights: boolean,
  summary_insights: boolean,
): Promise<InsightsNotifications> {
  const url = `${BASE_API_URL}/onboarding/insights-notifications/`;
  return await postJSON(url, { anomaly_insights, summary_insights });
}

export async function getConnectGitProviderData(): Promise<ConnectGitProviderResponse> {
  const url = `${BASE_API_URL}/integrations/connect-git-provider/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getDashboardData(since?: string, until?: string): Promise<DashboardResponse> {
  let url = `${BASE_API_URL}/dashboard/`;

  const params = new URLSearchParams();
  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }

  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function generateDashboardInsights(since?: string, until?: string): Promise<void> {
  const url = `${BASE_API_URL}/dashboard/insights/`;
  return await postJSON(url, { since, until });
}

export async function getSIPDashboardData(): Promise<SIPDashboardResponse> {
  const url = `${BASE_API_URL}/dashboard/sip/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getSIPProductRoadmapRadarData(): Promise<SIPProductRoadmapRadarResponse> {
  const url = `${BASE_API_URL}/dashboard/sip/product-roadmap-radar/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getOrganizationDeveloperGroups(page: number = 1): Promise<OrganizationDeveloperGroupsResponse> {
  const url = `${BASE_API_URL}/organization/developer-groups/?page=${page}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getOrganizationRepositoryGroups(page: number = 1): Promise<OrganizationRepositoryGroupsResponse> {
  const url = `${BASE_API_URL}/organization/repository-groups/?page=${page}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getConnectJiraData(is_onboarding: boolean = false): Promise<ConnectJiraResponse> {
  const url = `${BASE_API_URL}/integrations/connect-jira/?is_onboarding=${is_onboarding}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getOrganizationUsers(page: number = 1): Promise<OrganizationUsersResponse> {
  const url = `${BASE_API_URL}/organization/users/?page=${page}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function uploadDocuments(files: File[]): Promise<UploadDocumentsResponse> {
  const url = `${BASE_API_URL}/documents/upload/`;

  const formData = new FormData();
  for (const [index, file] of files.entries()) {
    formData.append(`file_${index}`, file);
  }

  return await sendMultipartFormData("POST", url, formData);
}

export async function getProductRoadmapData(repoGroupId: string): Promise<ProductRoadmapResponse> {
  const url = `${BASE_API_URL}/roadmap/?product=${repoGroupId}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getProductRoadmapFilters(): Promise<ProductRoadmapFiltersResponse> {
  const url = `${BASE_API_URL}/roadmap/filters`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getDailyMessage(
  date: Date,
  asEmail: boolean,
  messageFilter?: MessageFilter,
): Promise<DailyMessageResponse> {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const dateString = `${year}-${month}-${day}`;
  const params = new URLSearchParams();
  params.append("date", dateString);
  params.append("as-email", asEmail.toString());
  if (messageFilter) {
    if (messageFilter.significance_levels?.length) {
      params.append("significance_levels", messageFilter.significance_levels.toString());
    }
    if (messageFilter.repository_groups?.length) {
      params.append("repository_groups", messageFilter.repository_groups.toString());
    }
    if (messageFilter.ticket_categories?.length) {
      params.append("ticket_categories", messageFilter.ticket_categories.toString());
    }
  }

  let url = `${BASE_API_URL}/contextualization/daily-message`;
  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getTeamHealthData(): Promise<TeamHealthResponse> {
  const url = `${BASE_API_URL}/team-health/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getBudgetPerformanceData(): Promise<BudgetPerformanceResponse> {
  const url = `${BASE_API_URL}/budget/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getCodebaseExecutiveSummary(
  since?: string,
  until?: string,
): Promise<CodebaseExecutiveSummaryResponse> {
  let url = `${BASE_API_URL}/codebase-reports/executive-summary/`;

  const params = new URLSearchParams();
  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }

  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getCodebaseComplianceDetail(
  since?: string,
  until?: string,
): Promise<CodebaseComplianceDetailResponse> {
  let url = `${BASE_API_URL}/codebase-reports/compliance-detail/`;

  const params = new URLSearchParams();
  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }

  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getCodebaseProductDetail(since?: string, until?: string): Promise<CodebaseProductDetailResponse> {
  let url = `${BASE_API_URL}/codebase-reports/product-detail/`;

  const params = new URLSearchParams();
  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }

  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export const updateJiraProjectSelection = async (
  projectId: string,
  isSelected: boolean,
): Promise<{ status: string; is_selected: boolean }> => {
  const url = `${BASE_API_URL}/integrations/connect-jira/projects/${projectId}/selection/`;
  return await putJSON(url, { is_selected: isSelected });
};

export async function getDailyMessageFilter(): Promise<DailyMessageFilterResponse> {
  const url = `${BASE_API_URL}/contextualization/message-filter`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function updateDailyMessageFilter(messageFilter: MessageFilter): Promise<DailyMessageFilterResponse> {
  const url = `${BASE_API_URL}/contextualization/message-filter`;
  return await postJSON(url, { ...messageFilter });
}

export async function getRawContextualizationData(): Promise<string> {
  //HACK this is a temp solution, it's using BASE_URL and returning data as raw text
  const url = `${BASE_URL}/contextualization/data`;
  const response = await fetch(url);
  return response.text();
}

export async function getTicketCompletenessData(
  filters?: TicketCompletenessFilters,
  page: number = 1,
): Promise<TicketCompletenessResponse> {
  let url = `${BASE_API_URL}/contextualization/ticket-completeness`;

  const params = new URLSearchParams();
  params.append("page", page.toString());
  if (filters) {
    const keys = ["llm_category", "project_key", "stage", "sort_by", "sort_order", "quality_category"] as const;
    for (const key of keys) {
      const value = filters[key];
      if (value) params.append(key, value);
    }
  }
  if (params.size) url += `?${params.toString()}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getTicketCompletenessStatistics(
  projectKey?: string,
): Promise<TicketCompletenessStatisticsResponse> {
  let url = `${BASE_API_URL}/contextualization/ticket-completeness/statistics`;

  if (projectKey) {
    url += `?project_key=${encodeURIComponent(projectKey)}`;
  }

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getTicketCompletenessTicket(ticketId: string): Promise<TicketCompletenessTicketResponse> {
  const url = `${BASE_API_URL}/contextualization/ticket-completeness/ticket?ticket_id=${encodeURIComponent(ticketId)}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getTicketCompletenessTrendChart(
  fromDate: string,
  toDate: string,
  projectKey?: string,
): Promise<TicketCompletenessTrendChartResponse> {
  let url = `${BASE_API_URL}/contextualization/ticket-completeness/trend-chart?from_date=${fromDate}&to_date=${toDate}`;

  if (projectKey) {
    url += `&project_key=${encodeURIComponent(projectKey)}`;
  }

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getAnomalyInsightsData(
  filters?: AnomalyInsightsFilters,
  page: number = 1,
): Promise<AnomalyInsightsResponse> {
  const params = new URLSearchParams();
  params.append("page", page.toString());

  if (filters) {
    const keys = [
      "anomaly_types",
      "significance_scores",
      "repository_names",
      "project_names",
      "categories",
      "confidence_levels",
      "date_from",
      "date_to",
      "sort_by",
      "sort_order",
    ] as const;

    for (const key of keys) {
      const value = filters[key];
      if (Array.isArray(value) && value.length) params.append(key, value.join(","));
      else if (value) params.append(key, value.toString());
    }
  }

  const url = `${BASE_API_URL}/contextualization/anomaly-insights?${params.toString()}`;
  const response = await fetch(url);
  return parseApiResponse(response);
}
