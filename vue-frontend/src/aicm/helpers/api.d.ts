import type { IntegrationStatusMap } from "@/common/api.d";
import type { INode } from "vue3-treeview/dist/structure/INode";

interface CoreAIFields {
  percentage_ai_overall: number;
  percentage_ai_pure: number;
  percentage_ai_blended: number;
  percentage_human: number;
  code_num_lines: number;
}

interface AIFields extends CoreAIFields {
  not_evaluated_num_files: number;
  attested_num_lines: number;
  num_files?: number;
}

interface ROIFields {
  productivity_achievement: number;
  potential_productivity_captured: number;
  date_ai_fields: AIFields;
  cost_saved?: number;
  hours_saved?: number;
  tools_cost_saved_percentage?: number;
  debug_data?: Record<string, number>;
}

interface PaginatedResponse {
  count: number;
  total_pages: number;
  current_page: number;
  next_page: number;
  previous_page: number;
}

export interface PaginatedRepositoryFiles {
  next: string;
  previous: string;
  results: RepositoryFile[];
}

export interface RepositoryCommit extends AIFields {
  sha: string;
  date_time: string;
  languages: { [key: string]: number };
  language_list_str: string;
  analysis_num_files: number;
  total_num_lines: number;
}

export interface Repository extends AIFields {
  full_name: string;
  public_id: string;
  languages: { [key: string]: number };
  language_list_str: string;
  last_analysis_num_files: number;
  total_num_lines: number;
  date_ai_fields: CoreAIFields;
  until_commit?: RepositoryCommit;
}

export interface RepositoryCodeAttestation {
  public_id: string;
  code_hash: string;
  label: string;
  comment: string;
  attested_by: User;
  updated_at: string;
}

export interface RepositoryCodeAttestationAgreeAll {
  code_hash: string;
  label: string;
}

export interface RepositoryGroup extends AIFields, ROIFields {
  public_id: string;
  name: string;
  repositories: Repository[];
  rules: Rule[];
  rule_risk_list: [Rule, string][];
  charts_cumulative: Chart[];
  charts_daily: Chart[];
  usage_category: string;
  num_files: number;
  roi_enabled: boolean;
}

export interface RepositoriesResponse {
  repositories: RepositoryGroupDetail;
  integrations: IntegrationStatusMap;
}

export interface RepositoryGroupDetail {
  count: number;
  groups: RepositoryGroup[];
  ungrouped: any;
}

export interface Chart {
  id: string;
  label: string;
  data: {
    categories: string[];
    series: {
      name: string;
      data: number[];
    }[];
    isPercentage: boolean;
  };
}

export interface RepositoryFileChunkBlame {
  author: string;
  code_line_start: number;
  code_line_end: number;
}

export interface RepositoryFileChunk {
  name: string;
  label: string;
  is_not_evaluated: boolean;
  code_line_start: number;
  code_line_end: number;
  code: string[];
  code_hash: string;
  public_id: string;
  attestation: RepositoryCodeAttestation;
  blames: RepositoryFileChunkBlame[];
}

export interface RepositoryFile {
  file_path: string;
  relative_path: string;
  not_evaluated: boolean;
  public_id: string;
  shredded: boolean;
  chunks: RepositoryFileChunk[];
  chunks_ai_blended: number;
  chunks_ai_pure: number;
  chunks_human: number;
  chunks_not_evaluated: number;
  chunks_attested: number;
  chunks_code_loaded: boolean;
}

export interface RepositoryPullRequest {
  pr_number: number;
  head_commit_sha: string;
  analysis_num_files: number;
  not_evaluated_num_files: number;
  repository: Repository;
  updated_at: string;
  needs_composition_recalculation: boolean;
}

export interface RuleCondition {
  public_id: string;
  code_type: string;
  operator: string;
  percentage: number;
  condition_str: string;
}

export interface Rule {
  public_id: string;
  name: string;
  description: string;
  condition_mode: string;
  risk: string;
  apply_organization: boolean;
  conditions: RuleCondition[];
  rule_str: string;
}

export interface Node extends INode {
  root: boolean;
  file_path: string;
  children: string[];
}

export interface Tree {
  [key: string]: Node;
}

export interface User {
  public_id: string;
  full_name: string;
  email: string;
}

export interface DeveloperGroupsResponse {
  groups: DeveloperGroup[];
  integrations: IntegrationStatusMap;
}

export interface DeveloperGroup {
  public_id: string;
  name: string;
  developers_count: number;
  rule_risk_list: [Rule, string][];
  stats: CoreAIFields;
}

export interface DevelopersResponse extends PaginatedResponse {
  developers: Developer[];
}

export interface Developer {
  public_id: string;
  name: string;
  email: string;
}
