import logging
import re

import requests

from mvp.utils import retry_on_status_code

logger = logging.getLogger(__name__)


class BaseApi:
    # retry on 429 and 5XX, as some APIs are unstable or timeout
    @retry_on_status_code(max_retries=2, delay=60, status_codes=[429, 500, 502, 503, 504])
    def request(self, path, params=None, method="GET", headers=None, **kwargs):
        headers = headers if headers else self.get_headers()
        full_url = path.startswith("http")
        url = path if full_url else self.clean_url(f"{self.API_BASE_URL}/{path}")
        response = requests.request(method=method, url=url, headers=headers, params=params, **kwargs)
        try:
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception(
                "HTTP request failed",
                extra={
                    "url": url,
                    "method": method,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            raise
        return response

    def clean_url(self, url):
        """
        Clean double slashes except for the protocol
        """
        return re.sub(r"(?<!:)/{2}", "/", url)

    def get_headers(self):
        return []
