import time
from unittest.mock import Mock, patch

import requests
from django.test import TestCase

from compass.integrations.apis import GitHubApi, GitHubInstallationDoesNotExist


class TestGitHubApi(TestCase):
    def setUp(self):
        self.api = GitHubApi()

    @patch("compass.integrations.apis.BaseApi.request")
    @patch("compass.integrations.apis.GitHubApi.refresh_token")
    @patch("compass.integrations.apis.GitHubApi.sleep_on_rate_limit")
    def test_request_401_with_valid_refresh_token(self, mock_sleep_on_rate_limit, mock_refresh_token, mock_request):
        def side_effect(*args, **kwargs):
            if mock_request.call_count == 1:
                raise requests.exceptions.HTTPError(response=Mock(status_code=401))

            return {"data": {}}

        mock_request.side_effect = side_effect
        mock_refresh_token.side_effect = None
        mock_sleep_on_rate_limit.return_value = True
        self.api._refresh_token = ("dummy_installation_id", "dummy_app_id", "dummy_pem")
        response = self.api.request("dummy_path")

        mock_refresh_token.assert_called_once()
        mock_sleep_on_rate_limit.assert_called_once()
        assert mock_request.call_count == 2
        self.assertEqual(response, {"data": {}})

    @patch("compass.integrations.apis.BaseApi.request")
    @patch("compass.integrations.apis.GitHubApi.refresh_token")
    @patch("compass.integrations.apis.GitHubApi.sleep_on_rate_limit")
    def test_request_401_with_not_valid_refresh_token(self, mock_sleep_on_rate_limit, mock_refresh_token, mock_request):
        def side_effect(*args, **kwargs):
            if mock_request.call_count > 1:
                self.api._refresh_token = None
            raise requests.exceptions.HTTPError(response=Mock(status_code=401))

        mock_request.side_effect = side_effect
        mock_refresh_token.side_effect = None
        self.api._refresh_token = ("dummy_installation_id", "dummy_app_id", "dummy_pem")
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api.request("dummy_path")

        mock_refresh_token.assert_called_once()
        mock_sleep_on_rate_limit.assert_not_called()
        assert mock_request.call_count == 2

    @patch("compass.integrations.apis.BaseApi.request")
    @patch("compass.integrations.apis.GitHubApi.refresh_token")
    @patch("compass.integrations.apis.GitHubApi.sleep_on_rate_limit")
    def test_request_401_without_refresh_token(self, mock_sleep_on_rate_limit, mock_refresh_token, mock_request):
        mock_request.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=401))
        self.api._refresh_token = None
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api.request("dummy_path")

        mock_refresh_token.assert_not_called()
        mock_sleep_on_rate_limit.assert_not_called()
        assert mock_request.call_count == 1

    @patch("compass.integrations.apis.BaseApi.request")
    @patch(
        "compass.integrations.apis.GitHubApi.sleep_on_rate_limit",
        return_value=True,
    )
    def test_request_403_rate_limit(self, mock_sleep_on_rate_limit, mock_request):
        mock_request.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=403))
        mock_sleep_on_rate_limit.return_value = True
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.api.request("dummy_path")

        assert mock_sleep_on_rate_limit.call_count == 1
        assert mock_request.call_count == 1
        self.assertEqual(context.exception.response.status_code, 429)

    @patch("compass.integrations.apis.BaseApi.request")
    @patch(
        "compass.integrations.apis.GitHubApi.sleep_on_rate_limit",
        return_value=True,
    )
    def test_request_403_not_rate_limit(self, mock_sleep_on_rate_limit, mock_request):
        mock_request.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=403))
        mock_sleep_on_rate_limit.return_value = False
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.api.request("dummy_path")

        assert mock_sleep_on_rate_limit.call_count == 1
        assert mock_request.call_count == 1
        self.assertEqual(context.exception.response.status_code, 403)

    @patch("compass.integrations.apis.BaseApi.request")
    @patch(
        "compass.integrations.apis.GitHubApi.sleep_on_rate_limit",
        return_value=True,
    )
    def test_request_403_disconnected_installation(self, mock_sleep_on_rate_limit, mock_request):
        mock_request.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=403))
        mock_sleep_on_rate_limit.return_value = False
        with self.assertRaises(GitHubInstallationDoesNotExist):
            self.api.request("/app/installations/1234/access_tokens")

        mock_sleep_on_rate_limit.assert_not_called()
        assert mock_request.call_count == 1

    @patch("compass.integrations.apis.BaseApi.request")
    @patch("compass.integrations.apis.GitHubApi.sleep_on_rate_limit")
    def test_request_404(self, mock_sleep_on_rate_limit, mock_request):
        mock_request.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=404))
        with self.assertRaises(GitHubInstallationDoesNotExist):
            self.api.request("dummy_path")

        mock_sleep_on_rate_limit.assert_not_called()

    @patch("compass.integrations.apis.BaseApi.request")
    @patch("compass.integrations.apis.GitHubApi.sleep_on_rate_limit")
    def test_request_other_error(self, mock_sleep_on_rate_limit, mock_request):
        mock_request.side_effect = requests.exceptions.HTTPError(response=Mock(status_code=500))
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api.request("dummy_path")

        mock_sleep_on_rate_limit.assert_not_called()

    @patch("compass.integrations.apis.BaseApi.request")
    @patch("compass.integrations.apis.GitHubApi.sleep_on_rate_limit")
    def test_request_no_error(self, mock_sleep_on_rate_limit, mock_request):
        mock_request.return_value = {"data": {}}
        response = self.api.request("dummy_path")
        mock_sleep_on_rate_limit.assert_called_once()
        self.assertEqual(response, {"data": {}})

    def get_rate_limit_mock_response(self, remaining, reset=None):
        response = Mock()
        response.headers = {
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Reset": reset if reset != None else int(time.time()) + 10,
        }
        return response

    @patch("time.sleep", return_value=None)
    def assert_sleep_called(self, mock_sleep, remaining=0, reset=None):
        response = self.get_rate_limit_mock_response(remaining, reset)
        slept = self.api.sleep_on_rate_limit(response)
        self.assertTrue(slept)
        sleep_time = max(
            int(response.headers.get("X-RateLimit-Reset")) - int(time.time()),
            GitHubApi.RATE_LIMIT_MIN_SLEEP_TIME,
        )
        mock_sleep.assert_called_with(sleep_time)

    @patch("time.sleep", return_value=None)
    def test_rate_no_headers(self, mock_sleep):
        response = Mock()
        response.headers = {}
        slept = self.api.sleep_on_rate_limit(response)
        self.assertFalse(slept)
        mock_sleep.assert_not_called()

    @patch("time.sleep", return_value=None)
    def test_rate_limit_over_threshold(self, mock_sleep):
        slept = self.api.sleep_on_rate_limit(self.get_rate_limit_mock_response(GitHubApi.RATE_LIMIT_SAFE_THRESHOLD + 1))
        self.assertFalse(slept)
        mock_sleep.assert_not_called()

    def test_rate_limit_same_threshold(self):
        self.assert_sleep_called(remaining=GitHubApi.RATE_LIMIT_SAFE_THRESHOLD)

    def test_rate_limit_under_threshold(self):
        self.assert_sleep_called(remaining=GitHubApi.RATE_LIMIT_SAFE_THRESHOLD - 1, reset=time.time() + 80)

    def test_rate_limit_zero(self):
        self.assert_sleep_called(remaining=0, reset=time.time() + 100)
