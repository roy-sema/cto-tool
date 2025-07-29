from compass.integrations.apis import BaseRestApi


class SnykRestApi(BaseRestApi):
    API_BASE_URL = "https://api.snyk.io/rest"
    API_VERSION = "2023-08-04"

    PER_PAGE_MAX = 100

    def __init__(self, auth_token):
        self.auth_token = auth_token

    def list_projects(self, org_id, per_page=PER_PAGE_MAX, all_pages=False):
        response = self.request(
            f"orgs/{org_id}/projects",
            {
                "version": self.API_VERSION,
                "meta.latest_issue_counts": "true",
                "limit": per_page,
            },
        )
        projects, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(projects, links)

        return projects

    def get_organization(self, org_id):
        organization = self.request(f"orgs/{org_id}", {"version": self.API_VERSION})
        return organization

    def get_headers(self):
        return {
            "Authorization": f"token {self.auth_token}",
            "Accept": "application/vnd.api+json",
        }

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        response_data = response.json()

        if "errors" in response_data:
            raise Exception("Multiple errors occurred:", response_data["errors"])

        return response_data

    def parse_response(self, response):
        return (response["data"], response["links"])

    def get_next_link_url(self, next_link):
        return next_link
