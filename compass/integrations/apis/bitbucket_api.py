from dataclasses import dataclass
from typing import Dict, Tuple

import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth

from compass.integrations.apis import BaseRestApi
from mvp.utils import retry_on_exceptions


@dataclass(frozen=True)
class BitBucketApiConfig:
    workspace: str
    access_token: str
    refresh_token: str


class BitBucketApi(BaseRestApi):
    """
    BitBucket API.

    Note:
    BitBucket uuid are returned with curly brackets like this:
    '{38a7213f-01b5-4bc4-bd4c-c7c9d9a40288}'

    https://community.atlassian.com/t5/Bitbucket-articles/Working-with-UUIDs-and-their-curly-brackets-workspace-names-or/ba-p/2500759

    uuids are stored in CTO-Tool exactly how they are received
    so expect curly brackets in repository external ids.
    """

    API_BASE_URL = "https://api.bitbucket.org/2.0"

    DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

    CHECK_RUN_TITLE = "Sema GenAI Detector"

    OAUTH_KEY = settings.BITBUCKET_OAUTH_CONSUMER_KEY
    OAUTH_SECRET = settings.BITBUCKET_OAUTH_CONSUMER_SECRET
    OAUTH_BASE_URL = "https://bitbucket.org/site/oauth2"

    def __init__(self, config: BitBucketApiConfig):
        self.workspace = config.workspace
        self.access_token = config.access_token
        self.refresh_token = config.refresh_token

    @classmethod
    def get_oauth_access_token_by_code(cls, code: str) -> Tuple[str, str]:
        response = requests.post(
            f"{cls.OAUTH_BASE_URL}/access_token",
            data={
                "grant_type": "authorization_code",
                "code": code,
            },
            auth=HTTPBasicAuth(cls.OAUTH_KEY, cls.OAUTH_SECRET),
        )
        response.raise_for_status()
        response_data = response.json()
        return response_data["access_token"], response_data["refresh_token"]

    def refresh_tokens(self):
        refresh_token = self.refresh_token
        # Setting this to None to avoid potential infinite loop
        self.refresh_token = None

        response = self.request(
            f"{self.OAUTH_BASE_URL}/access_token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=HTTPBasicAuth(self.OAUTH_KEY, self.OAUTH_SECRET),
            method="POST",
        )

        self.access_token = response["access_token"]
        self.refresh_token = response["refresh_token"]

        return self.access_token, self.refresh_token

    @classmethod
    def get_installation_url(cls, client_id: str) -> str:
        return f"{cls.OAUTH_BASE_URL}/authorize?client_id={client_id}&response_type=code"

    def list_commits(
        self,
        workspace,
        repo,
        all_pages=False,
        return_links=True,
    ):
        response = self.request(f"repositories/{workspace}/{repo}/commits")
        commits, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(commits, links)

        return (commits, links) if return_links else commits

    def compare_commits(self, workspace, repo, base, head, all_pages=False):
        spec = f"{base}..{head}" if base != head else base
        response = self.request(f"/repositories/{workspace}/{repo}/diffstat/{spec}")
        files, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(files, links)

        return files

    def list_user_workspaces(self, all_pages=False):
        response = self.request(f"/workspaces")
        workspaces, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(workspaces, links)

        return workspaces

    def list_workspace_repositories(self, workspace, all_pages=False):
        response = self.request(f"repositories/{workspace}")
        repositories, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(repositories, links)

        return repositories

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    @retry_on_exceptions(
        exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    )
    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)

        # 204 (delete) has no content
        if response.status_code == 204:
            return None

        response_data = response.json()

        if "error" in response_data:
            raise Exception("Error occurred:", response_data["error"])

        return response_data

    def parse_response(self, response):
        if "values" not in response:
            return (response, {})

        next_url = response.get("next")
        links = {"next": {"url": next_url}} if next_url else {}
        return (response["values"], links)

    def list_repos_for_workspace(self, workspace_id, all_pages=False):
        response = self.request(f"repositories/{workspace_id}")
        repositories, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(repositories, links)

        return repositories

    def get_commits(self, workspace_id, repository_slug, all_pages=False):
        response = self.request(f"repositories/{workspace_id}/{repository_slug}/commits")
        workspaces, links = self.parse_response(response)

        if all_pages:
            return self.get_all_pages(workspaces, links)

        return workspaces

    def get_last_commit(self, workspace_id, repository_slug):
        commits = self.get_commits(workspace_id, repository_slug)
        if not commits:
            return None
        # Commits are already returned in reverse chronological
        # order (from the most recent to the oldest)
        return commits[0]

    def create_check_run(
        self,
        repo_full_name,
        head_sha,
        conclusion=None,
        details_url="",
        output=None,
    ):
        payload = {
            "key": head_sha,
            "name": self.CHECK_RUN_TITLE,
            "state": conclusion,
            "url": details_url,
        }
        if output:
            payload["description"] = self.format_output(output)

        response = self.request(
            f"/repositories/{repo_full_name}/commit/{head_sha}/statuses/build",
            json=payload,
            method="POST",
        )
        data, _ = self.parse_response(response)
        return data

    def update_check_run(
        self,
        repo_full_name,
        head_sha,
        check_run_id,
        conclusion=None,
        details_url=None,
        output=None,
    ):
        payload = {
            "key": head_sha,
            "name": self.CHECK_RUN_TITLE,
            "state": conclusion,
            "url": details_url,
        }
        if output:
            payload["description"] = self.format_output(output)

        response = self.request(
            f"/repositories/{repo_full_name}/commit/{head_sha}/statuses/build/{check_run_id}",
            json=payload,
            method="PUT",
        )
        data, _ = self.parse_response(response)
        return data

    @staticmethod
    def format_output(output: Dict) -> str:
        # Bitbucket's status checks only displays a single line of
        # text for description so returning output is not possible.
        return output["summary"]

    def get_repo_url(self, owner, repo_name):
        repository = self.request(f"/repositories/{owner}/{repo_name}")
        url = repository["links"]["clone"][0]["href"]
        return f"https://x-token-auth:{self.access_token}@" + url.split("@")[1]

    def get_pull_request_files(self, repo_full_name, pull_request_number):
        response = self.request(f"/repositories/{repo_full_name}/pullrequests/{pull_request_number}/diffstat")
        files, links = self.parse_response(response)
        all_files = self.get_all_pages(files, links)
        parse_files = []

        for _file in all_files:
            # No new file can happen if the file was removed
            if not _file["new"]:
                parse_files.append({"filename": _file["old"]["path"], "status": _file["status"]})
                continue

            if not _file["old"]:
                parse_files.append({"filename": _file["new"]["path"], "status": _file["status"]})
                continue

            old_file_path = _file["old"]["path"]
            new_file_path = _file["new"]["path"]
            if old_file_path == new_file_path:
                parse_files.append({"filename": old_file_path, "status": _file["status"]})
            else:
                parse_files.append({"filename": old_file_path, "status": _file["status"]})
                parse_files.append({"filename": new_file_path, "status": _file["status"]})
        return parse_files

    def get_pull_request_commits(
        self,
        repo_owner: str,
        repo_name: str,
        pr_number: int,
    ) -> list:
        response = self.request(f"/repositories/{repo_owner}/{repo_name}/pullrequests/{pr_number}/commits")
        commits, links = self.parse_response(response)
        return self.get_all_pages(commits, links)

    def list_repos(self, workspace):
        if not workspace:
            # To avoid listing public repos if workspace is not provided
            raise ValueError("Workspace can't be empty")
        return self.request(f"/repositories/{workspace}")

    def get_repository(self, repo_full_name: str) -> Dict:
        if not repo_full_name or not repo_full_name.strip():
            raise ValueError("Repository full name can't be empty")
        return self.request(f"/repositories/{repo_full_name}")

    def get_pull_request(self, repo_full_name: str, pr_number: int) -> Dict:
        if not repo_full_name or not repo_full_name.strip():
            raise ValueError("Repository full name can't be empty")
        return self.request(f"/repositories/{repo_full_name}/pullrequests/{pr_number}/")

    def get_repository_pull_requests(
        self,
        repo_owner: str,
        repo_name: str,
        state: str = None,
    ) -> list:
        params = {}
        if state:
            params["state"] = state

        response = self.request(
            f"/repositories/{repo_owner}/{repo_name}/pullrequests",
            params=params,
        )
        pull_requests, links = self.parse_response(response)
        return self.get_all_pages(pull_requests, links)

    def install_webhooks_for_workspace(self, workspace, webhook_secret):
        if self.is_webhook_installed(workspace):
            return None

        response = self.request(
            f"/workspaces/{workspace}/hooks",
            json={
                "description": self.CHECK_RUN_TITLE,
                "url": settings.BITBUCKET_WEBHOOK_URL,
                "active": True,
                "events": [
                    "pullrequest:created",
                    "pullrequest:updated",
                    "pullrequest:fulfilled",
                    "pullrequest:rejected",
                    "pullrequest:push",
                    "pullrequest:unapproved",
                ],
                "secret_set": True,
                "secret": webhook_secret,
            },
            method="POST",
        )
        return self.parse_response(response)

    def is_webhook_installed(self, workspace):
        response = self.request(f"/workspaces/{workspace}/hooks")
        webhooks, links = self.parse_response(response)
        all_webhooks = self.get_all_pages(webhooks, links)
        return any(hook["description"] == self.CHECK_RUN_TITLE for hook in all_webhooks)

    def delete_webhooks_for_workspace(self, workspace):
        response = self.request(f"/workspaces/{workspace}/hooks")
        webhooks, links = self.parse_response(response)
        all_webhooks = self.get_all_pages(webhooks, links)
        webhooks_to_delete = [
            webhook["uuid"] for webhook in all_webhooks if webhook["description"] == self.CHECK_RUN_TITLE
        ]
        for webhook_id in webhooks_to_delete:
            self.delete_webhook(workspace, webhook_id)

    def delete_webhook(self, workspace, webhook_id):
        self.request(
            f"/workspaces/{workspace}/hooks/{webhook_id}/",
            method="DELETE",
        )

    def post_pull_request_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        comment: dict,
    ):
        response = self.request(
            f"/repositories/{repo_full_name}/pullrequests/{pr_number}/comments",
            json={"content": {"raw": self.format_comment(comment)}},
            method="POST",
        )
        parsed_response, _ = self.parse_response(response)
        return parsed_response

    def format_comment(self, output: dict) -> str:
        return "\n\n".join(value for value in output.values())

    def get_current_user(self):
        return self.request("/user")

    def get_workspace_id(self):
        return self.request("/workspaces")[0]["slug"]

    def delete_comment(self, repo_full_name, pr_number, comment_id):
        self.request(
            f"/repositories/{repo_full_name}/pullrequests/{pr_number}/comments/{comment_id}",
            method="DELETE",
        )
