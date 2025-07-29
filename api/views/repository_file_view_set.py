from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from mvp.mixins import DecodePublicIdMixin
from mvp.models import RepositoryCommit, RepositoryFile
from mvp.serializers import RepositoryFileSerializer


class RepositoryFileCursorPagination(CursorPagination):
    ordering = ("not_evaluated", "file_path")
    page_size = 1000

    def get_next_link(self):
        link = super().get_next_link()
        return self.make_link_https(link)

    def get_previous_link(self):
        link = super().get_previous_link()
        return self.make_link_https(link)

    # HACK: in production, the EC2 instance communicates via HTTP with the load balancer
    #       Then the load balancer adds the HTTPS layer.
    #       Thus, for Django, requests are HTTP.
    #       This fixes 'Mixed Content' errors in the frontend.
    def make_link_https(self, link):
        if link and settings.SITE_DOMAIN.startswith("https://"):
            return link.replace("http://", "https://")

        return link


class RepositoryFileViewSet(
    viewsets.ViewSet,
    DecodePublicIdMixin,
    LoginRequiredMixin,
    PermissionRequiredMixin,
):
    permission_required = "mvp.can_view_pull_request_scans"
    lookup_url_kwarg = "file_pk_encoded"

    def get_serializer_context(self, sha, repo_pk, hydrated=False, extraData=False):
        commit = get_object_or_404(RepositoryCommit, sha=sha, repository__id=repo_pk)
        context = {"commit": commit, "hydrated": hydrated, "extraData": extraData}
        return context

    def list(self, request, pk_encoded=None, sha=None):
        current_org = request.current_organization
        repo_pk = self.decode_id(pk_encoded)

        queryset = RepositoryFile.objects.filter(
            commit__sha=sha,
            commit__repository__id=repo_pk,
            commit__repository__organization=current_org,
        ).prefetch_related("repositoryfilechunk_set")

        paginator = RepositoryFileCursorPagination()
        page_queryset = paginator.paginate_queryset(queryset, request)
        serializer = RepositoryFileSerializer(
            page_queryset, many=True, context=self.get_serializer_context(sha, repo_pk)
        )

        return paginator.get_paginated_response(serializer.data)

    def retrieve(self, request, pk_encoded=None, sha=None, file_pk_encoded=None):
        current_org = request.current_organization
        repo_pk = self.decode_id(pk_encoded)
        file_pk = self.decode_id(file_pk_encoded)
        extraData = bool(request.query_params.get("extraData", False))

        commit = RepositoryCommit.objects.get(sha=sha, repository__id=repo_pk)
        repository_file = get_object_or_404(
            RepositoryFile.objects.prefetch_related(
                "repositoryfilechunk_set",
                "repositoryfilechunk_set__attestation",
                "repositoryfilechunk_set__attestation__attested_by",
                "repositoryfilechunk_set__repositoryfilechunkblame_set",
                "repositoryfilechunk_set__repositoryfilechunkblame_set__author",
            ),
            pk=file_pk,
            commit=commit,
            commit__repository__organization=current_org,
        )

        serializer = RepositoryFileSerializer(
            repository_file,
            context=self.get_serializer_context(sha, repo_pk, hydrated=True, extraData=extraData),
        )

        return Response(serializer.data)
