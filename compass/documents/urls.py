from django.urls import path

from compass.documents.views import (
    GetDocumentView,
    ListDocumentsView,
    UploadDocumentsView,
)

urlpatterns = [
    path(
        "upload/",
        UploadDocumentsView.as_view(),
        name="compass_api_uploads_documents",
    ),
    path(
        "<str:public_id>",
        GetDocumentView.as_view(),
        name="compass_api_get_document",
    ),
    path(
        "",
        ListDocumentsView.as_view(),
        name="compass_api_list_documents",
    ),
]
