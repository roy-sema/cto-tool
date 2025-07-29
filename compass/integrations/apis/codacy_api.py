from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from compass.integrations.apis import BaseRestApi


class CodacyApi(BaseRestApi):
    API_BASE_URL = "https://app.codacy.com/api/v3"

    DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    PER_PAGE_MAX = 100

    def __init__(self, auth_token):
        self.auth_token = auth_token

    def list_commit_analysis_stats(self, provider, org_name, repo_name, num_days=None):
        params = {"days": num_days} if num_days else {}
        response = self.request(
            f"/analysis/organizations/{provider}/{org_name}/repositories/{repo_name}/commit-statistics",
            params,
        )

        stats, links = self.parse_response(response)
        return stats

    def list_organization_repositories_with_analysis(self, provider, org_name, per_page=PER_PAGE_MAX, all_pages=False):
        response = self.request(
            f"/analysis/organizations/{provider}/{org_name}/repositories",
            {"limit": per_page},
        )
        repositories, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(repositories, links)

        return repositories

    def list_security_items(self, provider, org_name, per_page=PER_PAGE_MAX, all_pages=False):
        response = self.request(
            f"/organizations/{provider}/{org_name}/security/items",
            {
                # TODO: filter by status, we are only interested in those open
                "limit": per_page,
            },
        )
        items, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(items, links)

        return items

    def list_user_organizations(self, per_page=PER_PAGE_MAX, all_pages=False):
        response = self.request(f"/user/organizations", {"limit": per_page})
        organizations, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(organizations, links)

        return organizations

    def get_headers(self):
        return {
            "api-token": f"{self.auth_token}",
            "Accept": "application/vnd.api+json",
        }

    def parse_response(self, response):
        json = response.json()
        data = json["data"]
        pagination = json.get("pagination")

        links = {}
        if pagination and "cursor" in pagination:
            cursor = pagination["cursor"]

            parsed_url = urlparse(response.url)
            params = parse_qs(parsed_url.query)
            params["cursor"] = [cursor]

            query = urlencode(params, doseq=True)
            next_url = urlunparse(
                (
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    query,
                    parsed_url.fragment,
                )
            )

            links["next"] = {"url": next_url}

        return (data, links)
