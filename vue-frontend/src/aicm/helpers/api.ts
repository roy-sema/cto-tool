import type {
  DeveloperGroupsResponse,
  DevelopersResponse,
  PaginatedRepositoryFiles,
  RepositoriesResponse,
  RepositoryCodeAttestation,
  RepositoryCodeAttestationAgreeAll,
  RepositoryFile,
} from "@/aicm/helpers/api.d";
import { BASE_URL, parseApiResponse, postJSON } from "@/common/api";

export async function getOrganizationMetrics(since?: string, until?: string): Promise<any> {
  let url = `${BASE_URL}/api/organization/metrics/`;

  const params = new URLSearchParams();
  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }

  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getRepositoryFiles(repoPkEncoded: string, commitSha: string): Promise<PaginatedRepositoryFiles> {
  const url = `${BASE_URL}/api/repositories/${repoPkEncoded}/commits/${commitSha}/files/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getRepositoryFilesNextPage(nextUrl: string): Promise<PaginatedRepositoryFiles> {
  const response = await fetch(nextUrl);
  return parseApiResponse(response);
}

export async function getRepositoryFileDetails(
  repoPkEncoded: string,
  commitSha: string,
  filePkEncoded: string,
): Promise<RepositoryFile> {
  const url = `${BASE_URL}/api/repositories/${repoPkEncoded}/commits/${commitSha}/files/${filePkEncoded}/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getRepositoriesComposition(since?: string, until?: string): Promise<any> {
  // TODO: add type for aiComposition
  let url = `${BASE_URL}/api/repositories/composition/`;

  const params = new URLSearchParams();
  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }

  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getPullRequestComposition(repoPkEncoded: string, prNumber: number): Promise<any> {
  // TODO: add type for aiComposition
  const url = `${BASE_URL}/api/repositories/${repoPkEncoded}/pulls/${prNumber}/composition/`;
  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function attestChunk(
  repoPkEncoded: string,
  codeHash: string,
  label: string,
  comment?: string,
): Promise<RepositoryCodeAttestation> {
  const url = `${BASE_URL}/api/repositories/${repoPkEncoded}/attestation/`;
  return postJSON(url, { code_hash: codeHash, label, comment });
}

export async function attestChunkAgreeAll(
  repoPkEncoded: string,
  attestations: RepositoryCodeAttestationAgreeAll[],
): Promise<RepositoryCodeAttestationAgreeAll[]> {
  const url = `${BASE_URL}/api/repositories/${repoPkEncoded}/attestation/agree-all/`;
  return postJSON(url, attestations);
}

export async function getRepositoryGroups(since?: string, until?: string): Promise<RepositoriesResponse> {
  let url = `${BASE_URL}/api/repositories/groups/`;

  const params = new URLSearchParams();
  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }
  if (params.size) url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getDeveloperGroups(
  since: Date | null = null,
  until: Date | null = null,
): Promise<DeveloperGroupsResponse> {
  let url = `${BASE_URL}/api/developers/groups/`;
  if (since && until) url += `?since=${since}&until=${until}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}

export async function getDevelopers(
  groupPublicId: string,
  order: string = "name",
  page: number = 1,
  since: Date | string | null = null,
  until: Date | string | null = null,
): Promise<DevelopersResponse> {
  let url = `${BASE_URL}/api/developers/groups/${groupPublicId}/developers/`;

  since = since instanceof Date ? since.toISOString() : since;
  until = until instanceof Date ? until.toISOString() : until;

  const params = new URLSearchParams();
  params.append("order", order);
  params.append("page", page.toString());

  if (since && until) {
    params.append("since", since);
    params.append("until", until);
  }

  url += `?${params.toString()}`;

  const response = await fetch(url);
  return parseApiResponse(response);
}
