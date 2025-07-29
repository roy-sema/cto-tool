import logging
import re
import time
from dataclasses import dataclass

import jwt
import requests
from django.conf import settings
from sentry_sdk import capture_exception, push_scope

from compass.integrations.apis import BaseRestApi
from mvp.utils import retry_on_exceptions

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitHubApiConfig:
    installation_id: str
    app_id: str = settings.GITHUB_APP_ID
    pem: str = settings.GITHUB_APP_PRIVATE_KEY_PATH


class GitHubInstallationDoesNotExist(Exception):
    pass


class GitHubApi(BaseRestApi):
    API_BASE_URL = "https://api.github.com"
    DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
    PER_PAGE_MAX = 100

    # We should wait 1 minute before retrying
    # https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api?apiVersion=2022-11-28#exceeding-the-rate-limit
    RATE_LIMIT_MIN_SLEEP_TIME = 60
    RATE_LIMIT_SAFE_THRESHOLD = 10

    def __init__(self, config: GitHubApiConfig = None):
        self.auth_token = None
        self._refresh_token = None

        if config:
            self.authenticate(config)

    def get_app_encoded_jwt_key(self, app_id, pem):
        """
        Generates an encoded JWT key for the app.
        Requires the private key signature.
        The key expires in 1 hour.
        """
        with open(pem, "rb") as pem_file:
            signing_key = jwt.jwk_from_pem(pem_file.read())

        payload = {
            # Github allows the exp to be at most 10 minutes in the future.
            # Otherwise it can return a 401 error on some setups
            # because it thinks that exp is a little further in the future
            # than it actually is. So we use 597 seconds instead of 600.
            "iat": int(time.time()),  # Issued at time
            "exp": int(time.time()) + 597,  # JWT expiration time in seconds
            "iss": app_id,  # GitHub App's identifier
        }

        jwt_instance = jwt.JWT()
        encoded_jwt = jwt_instance.encode(payload, signing_key, alg="RS256")

        return encoded_jwt

    def get_repo_url(self, repo_owner, repo_name):
        return f"https://oauth2:{self.auth_token}@github.com/{repo_owner}/{repo_name}.git"

    def list_repos(self, page=1, per_page=PER_PAGE_MAX, all_pages=False):
        response = self.request(
            f"installation/repositories",
            {"page": page, "per_page": per_page},
        )
        data, links = self.parse_response(response)

        data_key = "repositories"

        if all_pages:
            return self.get_all_pages(data[data_key], links, data_key=data_key)

        return data[data_key]

    def list_commits(
        self,
        owner_name,
        repo_name,
        branch,
        since=None,
        until=None,
        page=1,
        per_page=PER_PAGE_MAX,
        all_pages=False,
        return_links=True,
    ):
        params = {
            "page": page,
            "per_page": per_page,
            "sha": branch,
        }

        if since:
            params["since"] = since.strftime(self.DATE_FORMAT)

        if until:
            params["until"] = until.strftime(self.DATE_FORMAT)

        response = self.request(f"repos/{owner_name}/{repo_name}/commits", params)
        commits, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(commits, links)

        return (commits, links) if return_links else commits

    def compare_commits(
        self,
        owner_name,
        repo_name,
        base,
        head,
        page=1,
        per_page=PER_PAGE_MAX,
        all_pages=False,
    ):
        response = self.request(
            f"repos/{owner_name}/{repo_name}/compare/{base}...{head}",
            {"page": page, "per_page": per_page},
        )
        data, links = self.parse_response(response)

        data_key = "files"

        if all_pages:
            return self.get_all_pages(data[data_key], links, data_key=data_key)

        return data[data_key]

    def get_contributors_activity(self, owner_name, repo_name):
        """
        w - Start of the week, given as a Unix timestamp.
        a - Number of additions
        d - Number of deletions
        c - Number of commits
        """
        response = self.request(f"/repos/{owner_name}/{repo_name}/stats/contributors")
        contributors, links = self.parse_response(response)
        return contributors

    def get_languages(self, owner_name, repo_name):
        response = self.request(f"/repos/{owner_name}/{repo_name}/languages")
        languages, links = self.parse_response(response)
        return languages

    def get_installation_access_tokens(self, installation_id, app_id, pem):
        """
        Generates an access token for the installation.
        Requires the private key signature.
        The token expires in 1 hour.

        Documentation: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation#generating-an-installation-access-token
        """
        encoded_jwt = self.get_app_encoded_jwt_key(app_id, pem)

        response = self.request(
            f"/app/installations/{installation_id}/access_tokens",
            method="POST",
            headers={
                "Authorization": f"Bearer {encoded_jwt}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        access_token, links = self.parse_response(response)

        return access_token

    def authenticate(self, config: GitHubApiConfig):
        access_token = self.get_installation_access_tokens(config.installation_id, config.app_id, config.pem)
        self.auth_token = access_token["token"]
        self._refresh_token = (config.installation_id, config.app_id, config.pem)

    def refresh_token(self):
        installation_id, app_id, pem = self._refresh_token

        # Avoid loop if we can't get a new access token
        self._refresh_token = None

        self.authenticate(GitHubApiConfig(installation_id, app_id, pem))

    def get_headers(self):
        return {
            "Authorization": f"token {self.auth_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    @retry_on_exceptions(
        exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    )
    def request(self, *args, **kwargs):
        try:
            response = super().request(*args, **kwargs)
        except requests.exceptions.HTTPError as error:
            # Issue a new token if it expires
            if error.response.status_code == 401 and self._refresh_token:
                self.refresh_token()
                return self.request(*args, **kwargs)
            # On 403, check if it's a rate limit issue
            elif error.response.status_code == 403:
                # if request is for app access tokens, then installation doesn't exist anymore
                regex = r"\/app\/installations\/\d+\/access_tokens"
                if re.search(regex, args[0]):
                    raise GitHubInstallationDoesNotExist

                # raising 429 makes the decorator of BaseApi.request() to retry
                if self.sleep_on_rate_limit(error.response):
                    error.response.status_code = 429

                raise
            # On 404, installation doesn't exist anymore (revoked from GitHub)
            elif error.response.status_code == 404:
                raise GitHubInstallationDoesNotExist
            else:
                with push_scope() as scope:
                    scope.set_extra("response_headers", error.response.headers)
                    scope.set_extra("response_payload", error.response.json())

                    if error.response.status_code == 401:
                        logger.exception("Can't refresh token")

                    capture_exception(error)
                    raise

        self.sleep_on_rate_limit(response)

        return response

    def sleep_on_rate_limit(self, response):
        """
        Because we may have several processes at the same time,
        sleep if remaining requests is lower or equal than the safe threshold.
        Documentation: https://docs.github.com/en/rest/overview/resources-in-the-rest-api?apiVersion=2022-11-28#rate-limiting
        """
        remaining = response.headers.get("X-RateLimit-Remaining", None)
        if remaining is None:
            return False

        if int(remaining) <= self.RATE_LIMIT_SAFE_THRESHOLD:
            now = int(time.time())
            min_sleep = self.RATE_LIMIT_MIN_SLEEP_TIME
            reset_time = int(response.headers.get("X-RateLimit-Reset", now + min_sleep))
            sleep_time = max(reset_time - now, min_sleep)
            logger.warning(f"Sleeping {sleep_time}s to avoid hitting rate limit...")
            time.sleep(sleep_time)
            return True

        return False

    def create_check_run(
        self,
        repo_full_name,
        head_sha,
        status,
        conclusion=None,
        details_url="",
        output=None,
    ):
        """
        https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28
        Creates a GitHub check run.

        Parameters:
            repo_full_name (str): The full name of the repository in the format "owner/repo".
            head_sha (str): The SHA of the commit to associate the check with.
            status (str): The status of the check. Can be one of "queued", "in_progress", "completed", "waiting", "requested", "pending".
            conclusion (str, optional): The conclusion of the check. Can be one of: "action_required", "cancelled", "failure", "neutral", "success", "skipped", "stale", "timed_out"
            details_url (str, optional): The URL with more details about the check.
            output (dict, optional): The output of the check. This is a dictionary with the following keys: "title", "summary", "text", "annotations", "images"
        Returns:
            dict: The response from the GitHub API.
        """
        payload = {
            "name": "Sema GenAI Detector",
            "head_sha": head_sha,
            "status": status,
        }

        if details_url:
            payload["details_url"] = details_url
        if conclusion:
            payload["conclusion"] = conclusion
        if output:
            payload["output"] = output

        response = self.request(
            f"/repos/{repo_full_name}/check-runs",
            json=payload,
            method="POST",
        )
        data, _links = self.parse_response(response)
        return data

    def update_check_run(
        self,
        repo_full_name,
        status,
        check_run_id,
        conclusion=None,
        details_url=None,
        output=None,
    ):
        """
        https://docs.github.com/en/rest/checks/runs?apiVersion=2022-11-28
        Updates a GitHub check run.

        Parameters:
            repo_full_name (str): The full name of the repository in the format "owner/repo".
            status (str): The status of the check. Can be one of "queued", "in_progress", "completed", "waiting", "requested", "pending".
            check_run_id (int): The ID of the check run, provide it to update an existing.
            conclusion (str, optional): The conclusion of the check. Can be one of: "action_required", "cancelled", "failure", "neutral", "success", "skipped", "stale", "timed_out"
            details_url (str, optional): The URL with more details about the check.
            output (dict, optional): The output of the check. This is a dictionary with the following keys: "title", "summary", "text", "annotations", "images"
        Returns:
            dict: The response from the GitHub API.
        """

        payload = {"name": "Sema GenAI Detector", "status": status}

        # github api doesn't like empty or None values
        if conclusion:
            payload["conclusion"] = conclusion
        if details_url:
            payload["details_url"] = details_url
        if output:
            payload["output"] = output

        response = self.request(
            f"/repos/{repo_full_name}/check-runs/{check_run_id}",
            json=payload,
            method="PATCH",
        )
        data, _links = self.parse_response(response)
        return data

    def get_repository_pull_requests(
        self,
        repo_full_name,
        since=None,
        until=None,
        state=None,
        page=1,
        per_page=PER_PAGE_MAX,
        all_pages=False,
    ):
        params = {"page": page, "per_page": per_page}

        if since:
            params["since"] = since.strftime(self.DATE_FORMAT)

        if until:
            params["until"] = until.strftime(self.DATE_FORMAT)

        if state:
            params["state"] = state

        response = self.request(f"/repos/{repo_full_name}/pulls", params)

        data, _links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(data, _links)

        return data

    def get_pull_request_commits(
        self,
        repo_full_name,
        pull_request_number,
        page=1,
        per_page=PER_PAGE_MAX,
        all_pages=False,
    ):
        response = self.request(
            f"/repos/{repo_full_name}/pulls/{pull_request_number}/commits",
            {"page": page, "per_page": per_page},
        )
        data, _links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(data, _links)

        return data

    def get_pull_request_files(
        self,
        repo_full_name,
        pull_request_number,
        page=1,
        per_page=PER_PAGE_MAX,
        all_pages=False,
    ):
        response = self.request(
            f"/repos/{repo_full_name}/pulls/{pull_request_number}/files",
            {"page": page, "per_page": per_page},
        )
        data, _links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(data, _links)

        return data

    @staticmethod
    def get_installation_url(app_name, state=None):
        url = f"https://github.com/apps/{app_name}/installations/new"
        if state:
            url += f"?state={state}"

        return url

    def delete_installation(self):
        """
        Deletes an installation.
        Documentation: https://docs.github.com/en/rest/apps/apps#delete-an-installation
        """
        installation_id, app_id, pem = self._refresh_token
        encoded_jwt = self.get_app_encoded_jwt_key(app_id, pem)

        response = self.request(
            f"/app/installations/{installation_id}",
            method="DELETE",
            headers={
                "Authorization": f"Bearer {encoded_jwt}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        data, links = self.parse_response(response)

        return data

    def get_repository(self, repository_full_name):
        return self.request(f"repos/{repository_full_name}")

    def get_pull_request(self, repository_full_name, pull_request_number):
        return self.request(f"repos/{repository_full_name}/pulls/{pull_request_number}")
