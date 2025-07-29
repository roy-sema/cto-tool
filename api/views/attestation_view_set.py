import logging

import posthog
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from api.permissions import CanEditAttestationPermission
from api.tasks import RecalculateCommitAICompositionTask
from mvp.mixins import DecodePublicIdMixin
from mvp.models import (
    Repository,
    RepositoryCodeAttestation,
    RepositoryCommit,
    RepositoryFile,
    RepositoryFileChunk,
    RepositoryPullRequest,
)
from mvp.serializers import RepositoryCodeAttestationSerializer
from mvp.utils import start_new_thread

logger = logging.getLogger(__name__)


class AttestationViewSet(DecodePublicIdMixin, ModelViewSet):
    permission_classes = [IsAuthenticated, CanEditAttestationPermission]
    serializer_class = RepositoryCodeAttestationSerializer
    queryset = RepositoryCodeAttestation.objects.all()
    http_method_names = ["post"]

    def create(self, request, *args, **kwargs):
        repository_id = self.decode_id(kwargs["pk_encoded"])
        organization = request.current_organization
        repository = get_object_or_404(Repository, pk=repository_id, organization=organization)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        data["repository"] = repository
        data["attested_by"] = request.user

        try:
            attestation = RepositoryCodeAttestation.objects.get(repository=repository, code_hash=data["code_hash"])
            serializer.instance = attestation
            serializer.partial = kwargs.pop("partial", False)
            status_code = status.HTTP_200_OK
        except RepositoryCodeAttestation.DoesNotExist:
            status_code = status.HTTP_201_CREATED

        attestation = serializer.save()
        self.update_chunks([attestation], organization)

        return Response(serializer.data, status=status_code)

    @action(detail=False, methods=["post"], url_path="agree-all", url_name="agree_all")
    def agree_all(self, request, *args, **kwargs):
        repository_id = self.decode_id(kwargs["pk_encoded"])
        organization = request.current_organization
        repository = get_object_or_404(
            Repository,
            pk=repository_id,
            organization=request.current_organization,
        )

        serializer = RepositoryCodeAttestationSerializer(
            data=request.data,
            many=True,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        code_hashes = [attestation["code_hash"] for attestation in data]

        existing_code_hashes = list(
            RepositoryCodeAttestation.objects.filter(repository=repository, code_hash__in=code_hashes).values_list(
                "code_hash", flat=True
            )
        )

        attestations = []
        for attestation in data:
            if attestation["code_hash"] in existing_code_hashes:
                continue

            attestations.append(
                RepositoryCodeAttestation(
                    repository=repository,
                    attested_by=request.user,
                    **attestation,
                )
            )

            # Avoid duplicates, request may contain the same code_hash multiple times.
            existing_code_hashes.append(attestation["code_hash"])

        if attestations:
            attestations = RepositoryCodeAttestation.objects.bulk_create(attestations)
            self.update_chunks(attestations, organization)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def update_chunks(self, attestations, organization):
        attestations_code_hash_map = {attestation.code_hash: attestation for attestation in attestations}
        chunks = (
            RepositoryFileChunk.objects.filter(
                file__commit__repository__organization=organization,
                code_hash__in=attestations_code_hash_map.keys(),
            )
            .prefetch_related("file", "file__commit")
            .all()
        )

        file_ids = set()
        commits = set()
        previous_labels = {}
        updated_chunks = []  # bulk_update recommends passing a list of objects
        for chunk in chunks:
            previous_labels[chunk.pk] = chunk.get_label()
            file_ids.add(chunk.file.pk)
            commits.add(chunk.file.commit)
            chunk.attestation = attestations_code_hash_map[chunk.code_hash]
            updated_chunks.append(chunk)

        chunks.bulk_update(updated_chunks, ["attestation"])

        updated_at = attestations[0].updated_at

        # Update attested date for files and commits.
        RepositoryFile.objects.filter(id__in=file_ids).update(last_attested_at=updated_at)

        commit_ids = [commit.pk for commit in commits]
        RepositoryCommit.objects.filter(id__in=commit_ids).update(last_attested_at=updated_at)

        commit_shas = [commit.sha for commit in commits]
        RepositoryPullRequest.objects.filter(head_commit_sha__in=commit_shas).update(last_attested_at=updated_at)

        self.send_to_posthog(chunks, previous_labels)

        # In production there's a cron process that will execute this task.
        if settings.DEBUG or settings.TESTING:
            self.recalculate_ai_composition(list(commits))

    @start_new_thread
    def send_to_posthog(self, chunks, previous_labels):
        for chunk in chunks:
            previous_label = previous_labels[chunk.id]
            event = "attest_agree" if chunk.attestation.label == previous_label else "attest_override"
            posthog.capture(
                chunk.attestation.attested_by.email,
                event=event,
                properties={
                    "code_hash": chunk.attestation.code_hash,
                    "previous_label": previous_label,
                    "attest_label": chunk.attestation.label,
                },
            )

    @start_new_thread
    def recalculate_ai_composition(self, commits):
        RecalculateCommitAICompositionTask().run(commits)
