import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.views import View
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from sentry_sdk import capture_exception

from compass.documents.models import Document
from compass.documents.serializers import CreateDocumentSerializer, DocumentSerializer
from mvp.mixins import DecodePublicIdMixin
from mvp.services import EmailService
from mvp.utils import traceback_on_debug

logger = logging.getLogger(__name__)


class GetDocumentView(DecodePublicIdMixin, PermissionRequiredMixin, RetrieveAPIView):
    permission_required = "mvp.can_get_compass_document"
    queryset = Document.objects.all().order_by("created_at")
    serializer_class = DocumentSerializer

    def get_queryset(self):
        public_id = self.kwargs.get("public_id")
        document_id = self.decode_id(public_id)
        return self.queryset.filter(
            id=document_id,
            organization=self.request.current_organization,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = get_object_or_404(self.get_queryset())
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ListDocumentsView(DecodePublicIdMixin, PermissionRequiredMixin, ListAPIView):
    permission_required = "mvp.can_list_compass_documents"
    queryset = Document.objects.all().order_by("created_at")
    serializer_class = DocumentSerializer
    page_size = 50
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return self.queryset.filter(
            organization=self.request.current_organization,
        )

    def list(self, request, *args, **kwargs):
        paginator = self.pagination_class()
        paginator.page_size = self.page_size

        queryset = self.get_queryset()
        page = paginator.paginate_queryset(queryset, request)
        documents = self.get_serializer(page, many=True)

        response_data = {
            "count": paginator.page.paginator.count,
            "total_pages": paginator.page.paginator.num_pages,
            "current_page": paginator.page.number,
            "next_page": (paginator.page.next_page_number() if paginator.page.has_next() else 0),
            "previous_page": (paginator.page.previous_page_number() if paginator.page.has_previous() else 0),
            "documents": documents.data,
        }
        return Response(response_data)


class UploadDocumentsView(PermissionRequiredMixin, CreateAPIView):
    permission_required = "mvp.can_upload_compass_documents"
    serializer_class = CreateDocumentSerializer

    def post(self, request, *args, **kwargs):
        # TODO - add these to a queue?
        # This solution could be a problem if the user uploads a large number of files.
        # On solution would be to pop these onto queue. We'd need to add a status field
        # to the model to track the status of the upload.
        uploaded_files = []
        validation_errors = []
        validation_success = []
        for file in request.FILES.values():
            serializer = self.serializer_class(
                data={
                    "name": file.name,
                    "organization": request.current_organization.id,
                    "file": file,
                    "uploaded_by": request.user.id,
                }
            )
            if serializer.is_valid():
                serializer.save()
                validation_success.append(f"{file.name} uploaded successfully")
                uploaded_files.append(file.name)
            else:
                file_errors = serializer.errors.get("file")
                if file_errors:
                    error_message = ", ".join(file_errors)
                    validation_errors.append(f"{file.name} {error_message}")
                else:
                    validation_errors.append(f"{file.name} failed to upload")

        if uploaded_files:
            logger.info(
                f"User with id '{request.user.id}' "
                f"from organization '{request.current_organization.name}' "
                f"uploaded files: {uploaded_files}"
            )
            try:
                self.send_document_email(request.current_organization, request.user, uploaded_files)
            except Exception as e:
                traceback_on_debug()
                capture_exception(e)

        if validation_errors:
            return Response(
                {"successes": validation_success, "errors": validation_errors},
            )

        return Response({"successes": validation_success})

    def send_document_email(self, organization, user, files):
        file_list = "\n".join(files)
        EmailService.send_email(
            "SIP: Uploaded Documents",
            f"New documents uploaded by '{user.get_full_name()} <{user.email}>' at organization '{organization.name}':\n\n{file_list}",
            settings.DEFAULT_FROM_EMAIL,
            [settings.SUPPORT_EMAIL],
        )


class DocumentsSettingsView(LoginRequiredMixin, PermissionRequiredMixin, DecodePublicIdMixin, View):
    permission_required = "mvp.can_edit_settings"

    def get(self, request):
        return render(request, "mvp/settings/documents.html")
