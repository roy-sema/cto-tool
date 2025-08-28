import json
import logging

import requests
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Resends webhook. Useful for testing purposes and reprocessing failed webhooks."

    def add_arguments(self, parser):
        parser.add_argument("json_path", type=str, help="Path to the webhook JSON file.")

        parser.add_argument("endpoint_url", type=str, help="URL to send the webhook to.")

    def handle(self, *args, **options):
        json_path = options["json_path"]
        endpoint_url = options["endpoint_url"]

        confirmation = input(f"Are you sure you want to resend the webhook? (y/n): ")
        if confirmation.lower() != "y":
            self.stdout.write(self.style.ERROR("Deletion aborted"))
            return

        headers, payload = self.read_webhook_data(json_path)

        response = self.send_webhook(headers, payload, endpoint_url)

        logger.info(f"Response Status Code: {response.status_code}")
        logger.info(f"Response Content: {response.content}")

    def read_webhook_data(self, json_file_path):
        with open(json_file_path) as file:
            data = json.load(file)

        headers = data.get("headers", {})
        payload = data.get("payload", {})

        return headers, payload

    def send_webhook(self, headers, payload, endpoint_url):
        return requests.post(endpoint_url, headers=headers, json=payload)
