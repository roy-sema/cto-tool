import type { BasePaginatedResponse, IntegrationStatusMap } from "@/common/api.d";

type StatusColor = "green" | "yellow" | "red";

export interface Chart {
  categories: string[];
  series: {
    name: string;
    data: number[];
  }[];
}

export interface CodebaseModule {
  name: string;
  icon: string;
  connected: boolean;
}

export interface CodebaseModules {
  Product: {
    code_quality: CodebaseModule;
    process: CodebaseModule;
    team: CodebaseModule;
  };
  Compliance: {
    open_source: CodebaseModule;
    code_security: CodebaseModule;
    cyber_security: CodebaseModule;
  };
}

export interface ConnectGitProviderData {
  url: string;
  is_connected: boolean;
}

export interface Insight {
  action: string;
  description: string;
  level: string;
  percentile: number;
  phase: string;
  position: string;
  status: string;
  text: string;
  remediation: {
    hours: number;
    sprints: number;
    dollars: number;
  };
}

export interface Product {
  id: string;
  name: string;
}

export interface RoadmapItem {
  description: string;
  name: string;
  startDate: Date | null;
  endDate: Date | null;
  teams: OrganizationDeveloperGroup[];
}

export interface Score {
  color?: string;
  phase?: string;
  score: number;
}

export interface AnomalyMessage {
  audience: string;
  message_for_audience: string;
}

export interface Anomaly {
  insight: string;
  category: string;
  significance_score: string;
  confidence_level: string;
  evidence: string;
  resolution: string;
  messages: AnomalyMessage[];
}

export interface AnomaliesByRepo {
  [repoName: string]: Anomaly[];
}

export interface GroupedAnomaly {
  [repoGroupName: string]: AnomaliesByRepo;
}

interface JustificationDetails {
  justification: string;
  examples: string;
  percentage: number;
  justification_text: string;
  examples_text: string;
}

interface Justification {
  [category: string]: JustificationDetails;
}

interface GroupedJustification {
  [groupId: string]: Justification;
}

export interface DashboardResponse {
  chart: Chart;
  products: Product[];
  updated_at: number;
  org_first_date: string;
  integrations: IntegrationStatusMap;
  default_time_window_days: number;
  justifications: Justification;
  anomaly_insights: GroupedAnomaly;
  grouped_justifications: GroupedJustification;
  date_range: [number, number];
  repository_groups_url: string;
  since: string;
  until: string;
}

export interface SIPDashboardResponse {
  overall_ai: { percentge: number; color: string };
  score: Score;
  initiatives: { count: number };
}

export interface SIPProductRoadmapRadarResponse {
  updated_at: number;
  integrations: IntegrationStatusMap;
  initiatives: {
    updated_at: number;
    count: number;
  };
  development_activity: {
    updated_at: number;
    duration: number;
    activities: {
      name: string;
      percentage: number;
    }[];
  };
  daily_message: {
    updated_at: number;
  };
  raw_results: {
    updated_at: number;
  };
  ticket_completeness: {
    updated_at: number;
    average_score: number;
  };
  anomaly_insights: {
    updated_at: number;
  };
}

export interface ConnectGitProviderResponse {
  azure_devops: ConnectGitProviderData;
  bitbucket: ConnectGitProviderData;
  github: ConnectGitProviderData;
}

export interface JiraProject {
  name: string;
  public_id: string;
  is_selected: boolean;
  key: string;
}

export interface ConnectJiraResponse {
  url: string;
  is_connected: boolean;
  projects: JiraProject[];
}

export interface OrganizationDeveloperGroup {
  id: string;
  name: string;
}

export interface OrganizationRepositoryGroup {
  public_id: string;
  name: string;
}

export interface OrganizationUser {
  public_id: string;
  email: string;
}

export interface OrganizationDeveloperGroupsResponse extends BasePaginatedResponse {
  developer_groups: OrganizationDeveloperGroup[];
}

export interface OrganizationRepositoryGroupsResponse extends BasePaginatedResponse {
  repository_groups: OrganizationRepositoryGroup[];
}

export interface OrganizationUsersResponse extends BasePaginatedResponse {
  users: OrganizationUser[];
}

export interface UploadDocumentsResponse {
  successes: string[];
  errors?: string[];
}

export interface TeamMember {
  name: string;
  pic: string;
}

export interface Epic {
  name: string;
  description: string;
  percentage: number;
}

export interface Initiative {
  name: string;
  justification: string;
  percentage: number;
  epics: Epic[];
  percentage_tickets_done: number;
  tickets_done: number;
  tickets_total: number;
  start_date: string;
  estimated_end_date: string;
  delivery_estimate: string;
}

export interface ReconcilableInitiative {
  name: string;
  initiative_type: string;
  git_activity: string;
  jira_activity: string;
}

export interface ProductRoadmapResponse {
  roadmap_ready: boolean;
  updated_at: string;
  integrations: IntegrationStatusMap;
  initiatives: Initiative[];
  reconcilable_initiatives: ReconcilableInitiative[];
  summary: string;
  date_range: [number, number];
  default_time_window_days: number;
}

export interface ProductRoadmapFiltersResponse {
  repository_groups: OrganizationRepositoryGroup[];
}

export interface DailyMessageResponse {
  date: string;
  content: string;
}

export interface TeamHealthMetric {
  name: string;
  current: number;
  goal: number;
  max: number;
  postfix: string;
  status: string;
  color: StatusColor;
}

export interface TeamHealthResponse {
  updated_at: string;
  integrations: IntegrationStatusMap;
  metrics: TeamHealthMetric[];
  summary: string;
  insights: string[];
}

export interface BudgetPerformanceSubMetric {
  name: string;
  color: StatusColor;
  status: string;
}

export interface BudgetPerformanceMetric {
  name: string;
  current: number;
  total_budget: number;
  color: StatusColor;
  sub_metrics: BudgetPerformanceSubMetric[];
}

export interface BudgetPerformanceResponse {
  updated_at: string;
  integrations: IntegrationStatusMap;
  metrics: BudgetPerformanceMetric[];
  summary: string;
  insights: string[];
}

export interface CodebaseComplianceDetailResponse {
  chart_iradar_issues_cve: Chart;
  chart_iradar_submodules_with_risk: Chart;
  chart_snyk_issues_cve: Chart;
  chart_snyk_issues_license: Chart;
  chart_snyk_issues_sast: Chart;
  connections: Record<string, string>;
  default_time_window_days: number;
  insight_commits: Insight;
  insight_files: Insight;
  insight_high_cve: Insight;
  insight_high_sast: Insight;
  iradar_submodules_difference: {
    current: number;
    last_week: number;
  };
  modules: CodebaseModules;
  org_first_date: string | null;
  snyk_high_sast_issues: number;
  updated_at: number;
  since: string;
  until: string;
  integrations: IntegrationStatusMap;
}

export interface CodebaseExecutiveSummaryResponse {
  caveats: Record<string, string>;
  chart_iradar_issues_cve: Chart;
  chart_iradar_submodules_with_risk: Chart;
  chart_process_commits: Chart;
  chart_process_files: Chart;
  chart_sema_compliance_score: Chart;
  chart_sema_product_score: Chart;
  chart_sema_score: Chart;
  chart_snyk_issues_cve: Chart;
  chart_snyk_issues_license: Chart;
  chart_snyk_issues_sast: Chart;
  chart_team_developers_percentage: Chart;
  chart_team_developers: Chart;
  connections: Record<string, string>;
  default_time_window_days: number;
  insight_commits: Insight;
  insight_files: Insight;
  insight_high_cve: Insight;
  insight_high_sast: Insight;
  iradar_submodules_difference: {
    current: number;
    last_week: number;
  };
  modules: CodebaseModules;
  org_first_date: string | null;
  sema_compliance_score: Score;
  sema_product_score: Score;
  sema_score_diff: number | null;
  sema_score_last_week: Score | null;
  sema_score: Score;
  snyk_high_sast_issues: number;
  updated_at: number;
  since: string;
  until: string;
  integrations: IntegrationStatusMap;
}

export interface CodebaseProductDetailResponse {
  chart_codacy_complexity: Chart;
  chart_codacy_coverage_percentage: Chart;
  chart_codacy_coverage: Chart;
  chart_codacy_duplication: Chart;
  chart_codacy_issues: Chart;
  chart_process_commits: Chart;
  chart_process_files: Chart;
  chart_team_developers_percentage: Chart;
  chart_team_developers: Chart;
  connections: Record<string, string>;
  default_time_window_days: number;
  insight_commits: Insight;
  insight_files: Insight;
  modules: CodebaseModules;
  org_first_date: null;
  updated_at: number;
  since: string;
  until: string;
  integrations: IntegrationStatusMap;
}

export interface InsightsNotifications {
  anomaly_insights: boolean;
  summary_insights: boolean;
}

export interface DailyMessageFilterOption {
  id: string;
  name: string;
}

export interface DailyMessageTicketCategory {
  id: string;
  name: string;
}

export interface MessageFilter {
  significance_levels: string[];
  repository_groups: OrganizationRepositoryGroup[];
  ticket_categories: string[];
  day_interval: number;
}

export interface DailyMessageFilterResponse {
  options: {
    significance_levels: DailyMessageFilterOption[];
    repository_groups: OrganizationRepositoryGroup[];
    ticket_categories: DailyMessageTicketCategory[];
  };
  daily_message_filter: MessageFilter;
}

export interface TicketCompletenessItem {
  ticket_id: string;
  name: string;
  project_key: string;
  llm_category: string;
  stage: string;
  completeness_score: number;
  quality_category: string;
}

export interface TicketCompletenessResponse {
  results: TicketCompletenessItem[];
  count: number;
  current_page: number;
  total_pages: number;
  filter_options: {
    llm_categories: string[];
    project_keys: string[];
    stages: string[];
    quality_categories?: string[];
  };
}

export interface TicketCompletenessFilters {
  llm_category?: string;
  project_key?: string;
  stage?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  quality_category?: string;
}

export interface TicketCompletenessStatisticsData {
  active_tickets_count: number;
  low_score_underway_count: number;
  avg_completeness_score: number;
}

export interface TicketCompletenessStatisticsResponse {
  latest: TicketCompletenessStatisticsData;
  historical: TicketCompletenessStatisticsData;
}

export interface TicketCompletenessTicketDetail {
  ticket_id: string;
  name: string;
  description: string;
  assignee: string;
  completeness_score_explanation: string;
  project_key: string;
  llm_category: string;
  stage: string;
  completeness_score: number;
  quality_category: string;
  reporter: string;
}

export interface TicketCompletenessTicketResponse {
  current_data: TicketCompletenessTicketDetail;
  scores_history: Array<{
    date: string;
    score: number;
  }>;
  jira_url: string | null;
}

export interface TicketCompletenessTrendChartItem {
  date: string;
  ticket_count: number;
  avg_completeness_score?: number;
}

export interface TicketCompletenessTrendChartResponse {
  results: TicketCompletenessTrendChartItem[];
  organizational_benchmark?: number;
}
export interface AnomalyInsightsItem {
  anomaly_id: string;
  anomaly_type: string;
  significance_score: number;
  title: string;
  insight: string;
  category: string;
  confidence_level: string;
  ticket_categories: string[];
  created_at: string;
  repository_name?: string;
  project_name?: string;
}

export interface AnomalyInsightsResponse extends BasePaginatedResponse {
  results: AnomalyInsightsItem[];
  first_date: string;
  filter_options: {
    anomaly_types: string[];
    significance_scores: number[];
    repository_names: string[];
    project_names: string[];
    categories: string[];
  };
}

export interface AnomalyInsightsFilters {
  anomaly_types?: string[];
  significance_scores?: string[];
  repository_names?: string[];
  project_names?: string[];
  date_from?: string;
  date_to?: string;
  sort_by?: string;
  sort_order?: string | null; // null means unsorted
  categories?: string[];
  confidence_levels?: string[];
}
