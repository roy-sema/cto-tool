from compass.integrations.apis import BaseApi


class IRadarRestApi(BaseApi):
    API_BASE_URL = "https://scanner.i-radar.ai/api/v1"

    DATE_FORMAT = "%d %B %Y, %I:%M %p"

    def list_organizations(self):
        # TODO: pagination?
        response = self.request("vendor/organizations")
        return response["data"]

    def list_scans(self):
        # TODO: filter by date, pagination?
        response = self.request("vendor/scan/history")
        return response["data"]

    def list_targets(self):
        # TODO: pagination?
        response = self.request("vendor/targets")
        return response["data"]

    def set_auth_token(self, username, password):
        self.auth_token = None
        response = self.request(
            "user/signin",
            method="POST",
            data={
                "username": username,
                "password": password,
            },
        )
        self.auth_token = response["access_token"]

    def get_headers(self):
        if not self.auth_token:
            return {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }

        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        return response.json()
