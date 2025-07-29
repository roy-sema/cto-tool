import json

import requests
from sentry_sdk import capture_exception, push_scope

from mvp.utils import traceback_on_debug


# TODO: extend from BaseIntegration if Slack is offered to all customers
class SlackIntegration:
    MAX_MESSAGE_LENGTH = 3000
    MESSAGE_SAFETY_MARGIN = 100  # Can be used when truncating messages

    @staticmethod
    def send_webhook(webhook_url, blocks: list):
        payload = {"blocks": blocks}
        headers = {"Content-Type": "application/json"}

        try:
            response = requests.post(webhook_url, data=json.dumps(payload), headers=headers)
            if response.status_code != 200:
                raise ValueError(
                    f"Request to Slack returned an error {response.status_code}, the response is:\n{response.text}"
                )
        except Exception as error:
            traceback_on_debug()

            with push_scope() as scope:
                scope.set_extra("blocks", blocks)
                scope.set_extra("webhook_url", webhook_url)
                capture_exception(error)

    @staticmethod
    def get_markdown_block(text: str):
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        }

    @staticmethod
    def get_quote_block(header: str, text: str):
        return {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_quote",
                    "elements": [
                        {
                            "type": "text",
                            "text": f"{header}:\n",
                            "style": {"bold": True},
                        },
                        {"type": "text", "text": text},
                    ],
                },
            ],
        }
