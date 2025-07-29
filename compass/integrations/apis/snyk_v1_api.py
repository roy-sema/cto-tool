from compass.integrations.apis import BaseRestApi


class SnykV1Api(BaseRestApi):
    API_BASE_URL = "https://api.snyk.io/v1"

    DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

    PER_PAGE_MAX = 100

    def __init__(self, auth_token):
        self.auth_token = auth_token

    def project_history(self, org_id, project_id, per_page=PER_PAGE_MAX, all_pages=False):
        url = f"org/{org_id}/project/{project_id}/history/"
        response = self.request(url, {"perPage": per_page}, method="POST")
        data, links = self.parse_response(response)

        data_key = "snapshots"
        if all_pages:
            return self.get_all_pages(data[data_key], links, data_key=data_key)

        return data[data_key]

    def project_issues(self, org_id, project_id):
        url = f"org/{org_id}/project/{project_id}/aggregated-issues"
        payload = {
            "includeDescription": True,
            "includeIntroducedThrough": True,
        }
        response = self.request(url, method="POST", data=payload)
        data, links = self.parse_response(response)
        return data["issues"]

    def snapshot_issues(self, org_id, project_id, snapshot_id, types=[]):
        url = f"org/{org_id}/project/{project_id}/history/{snapshot_id}/aggregated-issues"
        payload = {
            "includeDescription": True,
            "includeIntroducedThrough": True,
        }
        if types:
            payload["filters"] = {"types": types}

        response = self.request(url, method="POST", data=payload)
        data, links = self.parse_response(response)
        return data["issues"]

    def licenses(self, org_id):
        response = self.request(f"/org/{org_id}/licenses", method="POST")
        data, links = self.parse_response(response)
        return data["results"]

    def get_headers(self):
        return {
            "Authorization": f"token {self.auth_token}",
            "Accept": "application/json",
        }
