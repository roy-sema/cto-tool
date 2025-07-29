import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from django.conf import settings
from django.utils.text import slugify
from rest_framework.views import APIView
from sentry_sdk import capture_exception, capture_message, push_scope

from api.parsers import BodySavingJSONParser
from api.tasks import ProcessPullRequestTask
from compass.integrations.integrations import GitBaseIntegration
from mvp.models import WebhookRequest
from mvp.utils import retry_on_exceptions, start_new_thread, traceback_on_debug

logger = logging.getLogger(__name__)


class WebhookDatabaseNotReadyError(Exception):
    pass


class BaseWebhookView(APIView, ABC):
    RESPONSE_ERROR = "Unexpected error, please try again"
    RESPONSE_SUCCESS = "Webhook received and processed successfully"
    RESPONSE_UNSUPPORTED_ACTION = "Unsupported action"

    parser_classes = [BodySavingJSONParser]
    permission_classes = []

    @abstractmethod
    def get_integration(self) -> GitBaseIntegration:
        pass

    @abstractmethod
    def post(self, request, *args, **kwargs):
        pass

    def dispatch(self, request, *args, **kwargs):
        webhook = None
        if request.method == "POST":
            webhook = self.store_webhook_data(request)

        response = super().dispatch(request, *args, **kwargs)

        if webhook:
            try:
                webhook.response_status_code = response.status_code
                webhook.response_message = response.data
                webhook.save()
            except Exception as error:
                traceback_on_debug()
                capture_exception(error)

        return response

    @retry_on_exceptions(exceptions=(WebhookDatabaseNotReadyError,))
    def store_webhook_data(self, request):
        integration = self.get_integration()
        try:
            provider_name = integration.provider.name
        except AttributeError:  # This can happen on deployments where the database isn't ready yet.
            raise WebhookDatabaseNotReadyError

        headers = None
        payload = None

        try:
            headers, payload = self.get_webhook_request_data(request)
            file_path = self.write_webhook_request_to_file(
                request,
                provider_name,
                headers,
                payload,
                integration.WEBHOOK_REQUEST_HEADER_ID,
            )
            if not file_path:
                return None

            return WebhookRequest.objects.create(
                provider=integration.provider,
                data_file_path=file_path,
            )
        except Exception as error:
            with push_scope() as scope:
                scope.set_extra("provider", provider_name)
                if headers and payload:
                    scope.set_extra("headers", headers)
                    scope.set_extra("payload", payload)
                traceback_on_debug()
                capture_exception(error)

    def get_webhook_request_data(self, request):
        return dict(request.headers), json.loads(request.body.decode("utf-8"))

    def write_webhook_request_to_file(self, request, provider_name, headers, payload, header_request_id="x-request-id"):
        folder = self.make_webhook_request_directory()

        request_id = request.headers.get(header_request_id)
        if not request_id:
            with push_scope() as scope:
                scope.set_extra("provider", provider_name)
                scope.set_extra("headers", headers)
                capture_message(f"Can't fetch header f{header_request_id}")

            request_id = str(uuid.uuid4())

        file_path = os.path.join(
            str(folder),
            f"{slugify(provider_name)}-{slugify(request_id)}.json",
        )
        if os.path.exists(file_path):
            return None

        with open(file_path, "w") as f:
            f.write(json.dumps({"headers": headers, "payload": payload}))

        return file_path

    def make_webhook_request_directory(self):
        now = datetime.now()
        folder = os.path.join(
            settings.WEBHOOK_DATA_DIRECTORY,
            *[str(now.strftime(_format)) for _format in ["%Y", "%m", "%d", "%H"]],
        )

        os.makedirs(folder, exist_ok=True)

        return folder

    @start_new_thread
    def process_pull_request_background(self, request_data, integration):
        ProcessPullRequestTask().run(request_data, integration)
