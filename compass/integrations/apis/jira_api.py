import logging
from dataclasses import dataclass

import requests
from django.conf import settings

from compass.integrations.apis import BaseApi
from mvp.utils import retry_on_exceptions

logger = logging.getLogger(__name__)


class JiraApiException(Exception):
    pass


class JiraRefreshTokenException(Exception):
    pass


@dataclass(frozen=True)
class JiraApiConfig:
    access_token: str
    refresh_token: str
    cloud_id: str = None


class JiraApi(BaseApi):
    OAUTH_BASE_URL = "https://auth.atlassian.com"
    API_BASE_URL = "https://api.atlassian.com"
    PAGINATION_MAX_RESULTS = 50

    # Permissions should match what is in the Jira consumer
    PERMISSIONS = [
        "offline_access",  # required for refresh token
        "read:me",
        "read:account",
        "read:jira-work",
        "manage:jira-project",
        "manage:jira-configuration",
        "read:jira-user",
        "write:jira-work",
        "manage:jira-webhook",
        "manage:jira-data-provider",
        "read:servicedesk-request",
        "manage:servicedesk-customer",
        "write:servicedesk-request",
        "read:servicemanagement-insight-objects",
    ]
    PERMISSION_SCOPES = " ".join(PERMISSIONS)

    def __init__(self, config: JiraApiConfig):
        self.access_token = config.access_token
        self.refresh_token = config.refresh_token
        self.cloud_id = config.cloud_id

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    @retry_on_exceptions(
        exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    )
    def request(self, *args, **kwargs):
        return super().request(*args, **kwargs)

    def get_path_with_cloud_id(self, path):
        """
        Most API calls, once the initial connection
        is created, will be using Jira's REST v3 API.
        https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/#about

        Because we are using Oauth to authenticate we need to amend
        the URL as described in the documentation and add the cloud_id:
        https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/#other-integrations

        The cloud_id is obtained during the initial
        connection via the get_accessible_resources method.

        An example of how to use this would be:
        For the API call to get users, in documentation we see this here:
        https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-users/#api-rest-api-3-users-search-get

        The URL stated is:
        https://your-domain.atlassian.net/rest/api/3/users/search

        However, because we are using Oauth we would need to parse the URL to be:
        f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/users/search"

        To get this path provide this method with the path '/users/search'
        For example:
            self.get_path_with_cloud_id('/users/search')
        """
        if not self.cloud_id:
            raise JiraApiException("Missing cloud ID")

        return f"/ex/jira/{self.cloud_id}/rest/api/3{path}"

    @classmethod
    def get_installation_url(cls, state_secret):
        return (
            f"{cls.OAUTH_BASE_URL}/authorize"
            f"?audience=api.atlassian.com"
            f"&client_id={settings.JIRA_OAUTH_CONSUMER_KEY}"
            f"&scope={cls.PERMISSION_SCOPES}"
            f"&redirect_uri={settings.JIRA_OAUTH_REDIRECT_URL}"
            f"&state={state_secret}"
            f"&response_type=code"
            f"&prompt=consent"
        )

    @classmethod
    @retry_on_exceptions(
        exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    )
    def get_access_and_refresh_tokens(cls, auth_code):
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.JIRA_OAUTH_CONSUMER_KEY,
            "client_secret": settings.JIRA_OAUTH_CONSUMER_SECRET,
            "code": auth_code,
            "redirect_uri": settings.JIRA_OAUTH_REDIRECT_URL,
        }
        return requests.post(
            f"{cls.OAUTH_BASE_URL}/oauth/token",
            json=data,
        )

    @retry_on_exceptions(
        exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    )
    def refresh_tokens(self):
        refresh_token = self.refresh_token
        # Setting this to None to avoid potential infinite loop
        self.refresh_token = None

        data = {
            "grant_type": "refresh_token",
            "client_id": settings.JIRA_OAUTH_CONSUMER_KEY,
            "client_secret": settings.JIRA_OAUTH_CONSUMER_SECRET,
            "refresh_token": refresh_token,
        }
        response = requests.post(
            f"{self.OAUTH_BASE_URL}/oauth/token",
            json=data,
        )
        if not response.ok:
            raise JiraRefreshTokenException(response.json())

        self.access_token = response.json()["access_token"]
        self.refresh_token = response.json()["refresh_token"]
        return self.access_token, self.refresh_token

    def get_accessible_resources(self):
        """
        This is used on connection to obtain the
        cloud ID which is used in future API calls.
        """
        response = self.request(
            path="/oauth/token/accessible-resources",
            headers=self.get_headers(),
        )
        return response.json()

    def get_account(self):
        response = self.request(
            path="/me",
            headers=self.get_headers(),
        )
        return response.json()

    def get_users(self):
        """
        Using this endpoint to get users as Jira's /user/bulk endpoint is
        experimental and doesn't seem to be working (returns 400, empty response).

        But this endpoint doesn't return a paginated response.
        As in there are missing 'maxResults', 'startAt', 'nextPage' etc fields.

        Currently this endpoint returns a maximum of 50 users.
        # TODO - find a way to get all users
        """
        return self.request(
            path=self.get_path_with_cloud_id("/users/search"),
            headers=self.get_headers(),
        )

    def get_projects(self):
        response = self.request(
            path=self.get_path_with_cloud_id("/project/search"),
            headers=self.get_headers(),
            params={"startAt": 0, "maxResults": self.PAGINATION_MAX_RESULTS},
        )
        return self.parse_paginated_response(response)

    @retry_on_exceptions(
        exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    )
    def parse_paginated_response(self, response):
        """
        Some Jira API endpoints return paginated responses.

        https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/#pagination
        """
        response_json = response.json()
        values = response_json["values"]

        while response_json.get("nextPage"):
            response = requests.get(
                response_json["nextPage"],
                headers=self.get_headers(),
            )
            response_json = response.json()
            values += response_json["values"]

        return values

    def get_service_info(self):
        response = self.request(
            path=self.get_path_with_cloud_id("/serverInfo"),
            headers=self.get_headers(),
        )
        if not response.ok:
            logger.exception(
                "Failed to get service info due to response code is not 200",
                extra={"response_code": response.status_code},
            )
            return None
        return response.json()

    def get_organization_url(self):
        """
        Returns the organization URL for the Jira connection.
        """
        service_info = self.get_service_info()
        if not service_info:
            return None
        base_url = service_info.get("baseUrl")
        if not base_url:
            logger.exception(
                "baseUrl not found in Jira service info response",
                extra={"service_info": service_info},
            )
            return None
        return base_url
