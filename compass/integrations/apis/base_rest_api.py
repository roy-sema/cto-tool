import logging

import requests

from .base_api import BaseApi

logger = logging.getLogger(__name__)


class BaseRestApi(BaseApi):
    def parse_response(self, response):
        try:
            return response.json(), response.links
        except requests.exceptions.JSONDecodeError as error:
            if response.status_code == 204:
                return {}, {}
            else:
                logger.exception("Can't parse JSON response", extra={"response": response})
                raise

    def get_all_pages(self, records, links, data_key=None):
        while "next" in links:
            next_url = self.get_next_link_url(links["next"])
            data, links = self.parse_response(self.request(next_url))
            records.extend(data[data_key] if data_key else data)

        return records

    def get_next_link_url(self, next_link):
        return next_link.get("url", None)
