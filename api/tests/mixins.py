import json
import os

TEST_DATA_DIRECTORY = "api/tests/data/webhooks/"


class WebhooksDataTestMixin:
    WEBHOOK_OPENED = "opened"
    WEBHOOK_MERGED = "merged"
    WEBHOOK_NOT_MERGED = "notmerged"
    WEBHOOK_REOPENED = "reopened"
    WEBHOOK_SYNCHRONIZE = "synchronize"

    WEBHOOK_LIST = [
        WEBHOOK_OPENED,
        WEBHOOK_MERGED,
        WEBHOOK_NOT_MERGED,
        WEBHOOK_REOPENED,
        WEBHOOK_SYNCHRONIZE,
    ]

    WEBHOOK_PROVIDER_GITHUB = "github"
    WEBHOOK_PROVIDER_AZURE_DEVOPS = "azure_devops"
    WEBHOOK_PROVIDER_BITBUCKET = "bitbucket"

    @classmethod
    def get_webhooks_test_data(cls, provider_dir_name):
        webhooks = {}
        provider_dir = os.path.join(TEST_DATA_DIRECTORY, provider_dir_name)
        for file_name in os.listdir(provider_dir):
            if not file_name.endswith(".json"):
                continue

            file_path = os.path.join(provider_dir, file_name)
            request_data = json.load(open(file_path))
            action = file_name.split("_")[-1].replace(".json", "")
            webhooks[action] = request_data

        return webhooks
