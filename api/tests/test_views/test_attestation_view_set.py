from unittest.mock import patch

from django.contrib.auth.models import Group
from django.urls import reverse
from parameterized import parameterized

from compass.integrations.integrations import GitHubIntegration
from mvp.models import (
    CodeGenerationLabelChoices,
    CustomUser,
    Organization,
    Repository,
    RepositoryCodeAttestation,
    RepositoryCommit,
    RepositoryFile,
    RepositoryFileChunk,
    RepositoryPullRequest,
)
from mvp.tests.test_views.base_view_test import BaseViewTestCase
from mvp.utils import round_half_up


class TestAttestationViewSet(BaseViewTestCase):
    def setUp(self):
        self.credentials = {
            "email": "testuser@domain.com",
            "password": "testpass456",
        }

        self.organization = Organization.objects.create(name="TestOrg")
        self.user = CustomUser.objects.create_user(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

        owner_group = Group.objects.get(name="Owner")
        owner_group.user_set.add(self.user)
        self.user.organizations.add(self.organization)

        (
            self.repository,
            self.commits,
            self.pr,
            self.commit_file_chunks,
            self.pr_metadata,
            self.commit_original_ai_fields,
        ) = self.create_repository_data(self.organization, "test")

        self.patcher = patch("api.tasks.RecalculateCommitAICompositionTask.update_status_checks")
        self.mock_update_status_checks = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def create_repository_data(self, organization, prefix):
        commits_sha = [f"{prefix}_sha1", f"{prefix}_sha2"]

        repository = Repository.objects.create(
            organization=organization,
            provider=GitHubIntegration().provider,
            external_id=f"{prefix}_external_id",
            owner=organization.name,
            name=f"{prefix}_repo",
            last_commit_sha=commits_sha[0],
        )

        commits = [
            RepositoryCommit.objects.create(
                repository=repository,
                sha=commits_sha[0],
                date_time="2024-01-01T00:00:00Z",
            ),
            RepositoryCommit.objects.create(
                repository=repository,
                sha=commits_sha[1],
                date_time="2024-01-02T00:00:00Z",
            ),
        ]

        pr = RepositoryPullRequest.objects.create(
            repository=repository,
            pr_number=1,
            base_commit_sha=commits[0].sha,
            head_commit_sha=commits[1].sha,
        )

        commits[1].pull_requests.add(pr)

        file_paths = [f"/{prefix}/file1", f"/{prefix}/file2"]
        commit_files = [
            [
                RepositoryFile.objects.create(
                    commit=commits[0],
                    file_path=file_paths[0],
                ),
                RepositoryFile.objects.create(
                    commit=commits[0],
                    file_path=file_paths[1],
                ),
            ],
            [
                RepositoryFile.objects.create(
                    commit=commits[1],
                    file_path=file_paths[0],
                )
            ],
        ]

        pr_metadata = {"changed_files": [{"filename": commit_files[1][0].file_path.lstrip("/")}]}

        commit_files_chunks_data = [
            [
                [
                    (20, 0, CodeGenerationLabelChoices.HUMAN),
                    (20, 20, CodeGenerationLabelChoices.AI),
                    (20, 20, CodeGenerationLabelChoices.BLENDED),
                ],
                [
                    (20, 0, CodeGenerationLabelChoices.HUMAN),
                    (20, 20, CodeGenerationLabelChoices.AI),
                    (20, 20, CodeGenerationLabelChoices.BLENDED),
                ],
            ],
            [
                # in second commit, Pure and Blended increase in first file
                [
                    (10, 0, CodeGenerationLabelChoices.HUMAN),
                    (25, 25, CodeGenerationLabelChoices.AI),
                    (25, 25, CodeGenerationLabelChoices.BLENDED),
                ]
            ],
        ]

        commit_file_chunks = []
        commit_original_ai_fields = []

        for commit_index, files in enumerate(commit_files_chunks_data):
            commit_file_chunks.append([])
            for file_index, chunks in enumerate(files):
                commit_file_chunks[commit_index].append([])

                file = commit_files[commit_index][file_index]

                line_start = 0
                for chunk_index, (num_lines, ai_num_lines, label) in enumerate(chunks):
                    chunk = RepositoryFileChunk.objects.create(
                        file=file,
                        name="",
                        code_hash=f"{file.file_path}_{chunk_index}",  # same hash in different commits
                        code_line_start=line_start + 1,
                        code_line_end=line_start + num_lines,
                        code_num_lines=num_lines,
                        code_ai_num_lines=ai_num_lines,
                        code_generation_label=label,
                    )
                    commit_file_chunks[commit_index][file_index].append(chunk)
                    line_start += num_lines

                file_ai_fields = self.calculate_chunks_ai_composition(commit_file_chunks[commit_index][file_index])
                self.update_ai_fields(file, file_ai_fields)

            commit_ai_fields = self.calculate_chunks_ai_composition(
                self.get_commit_files_chunks(commit_file_chunks[commit_index])
            )
            self.update_ai_fields(commits[commit_index], commit_ai_fields)
            commit_original_ai_fields.append(commit_ai_fields)

            if commits[commit_index].sha == repository.last_commit_sha:
                self.update_ai_fields(repository, commit_ai_fields)

            if commits[commit_index].sha == pr.head_commit_sha:
                self.update_ai_fields(pr, commit_ai_fields)

        return (
            repository,
            commits,
            pr,
            commit_file_chunks,
            pr_metadata,
            commit_original_ai_fields,
        )

    def get_commit_files_chunks(self, commit_file_chunks):
        return [chunk for file_chunks in commit_file_chunks for chunk in file_chunks]

    def update_ai_fields(self, instance, ai_fields):
        for attr, value in ai_fields.items():
            setattr(instance, attr, value)

        instance.save()

    def calculate_chunks_ai_composition(self, chunks):
        total_lines = 0
        total_ai_lines = 0
        num_lines_ai = 0
        num_lines_blended = 0
        num_lines_pure = 0

        for chunk in chunks:
            total_lines += chunk.code_num_lines

            if chunk.is_not_evaluated or chunk.is_labeled_human:
                continue

            total_ai_lines += chunk.code_ai_num_lines
            num_lines_ai += chunk.code_ai_num_lines

            label = chunk.get_label()
            if label == CodeGenerationLabelChoices.BLENDED:
                num_lines_blended += chunk.code_ai_num_lines
            elif label == CodeGenerationLabelChoices.AI:
                num_lines_pure += chunk.code_ai_num_lines

        return {
            "code_num_lines": total_lines,
            "code_ai_num_lines": num_lines_ai,
            "code_ai_blended_num_lines": num_lines_blended,
            "code_ai_pure_num_lines": num_lines_pure,
            "code_ai_percentage": round_half_up(total_ai_lines / total_lines * 100, 2),
            "code_ai_blended_percentage": round_half_up(num_lines_blended / total_lines * 100, 2),
            "code_ai_pure_percentage": round_half_up(num_lines_pure / total_lines * 100, 2),
        }

    def get_instance_ai_fields(self, instance):
        return {
            "code_num_lines": float(instance.code_num_lines),
            "code_ai_num_lines": float(instance.code_ai_num_lines),
            "code_ai_blended_num_lines": float(instance.code_ai_blended_num_lines),
            "code_ai_pure_num_lines": float(instance.code_ai_pure_num_lines),
            "code_ai_percentage": float(instance.code_ai_percentage),
            "code_ai_blended_percentage": float(instance.code_ai_blended_percentage),
            "code_ai_pure_percentage": float(instance.code_ai_pure_percentage),
        }

    def set_chunk_label(self, chunk, label):
        # update label and num lines, but don't save it
        chunk.code_ai_num_lines = 0 if label == CodeGenerationLabelChoices.HUMAN else chunk.code_num_lines
        chunk.code_generation_label = label

    def assert_ai_fields_equal(self, ai_fields1, ai_fields2):
        for key, value in ai_fields1.items():
            # prevent floating point errors
            self.assertAlmostEqual(value, ai_fields2[key], delta=0.001)

    def login(self):
        self.client.login(
            email=self.credentials["email"],
            password=self.credentials["password"],
        )

    def post_attestation(self, repository, code_hash, label, comment=None):
        payload = {"code_hash": code_hash, "label": label}
        if comment:
            payload["comment"] = comment

        return self.client.post(
            reverse(
                "attestation-list",
                kwargs={"pk_encoded": repository.public_id()},
            ),
            payload,
        )

    def get_attestation(self, repository, code_hash):
        try:
            return RepositoryCodeAttestation.objects.get(
                repository=repository,
                code_hash=code_hash,
            )
        except RepositoryCodeAttestation.DoesNotExist:
            return None

    @patch("api.tasks.RecalculateCommitAICompositionTask.run", return_value=({}, set()))
    def test_create(self, mock_recalculate_composition):
        self.login()

        chunk = self.commit_file_chunks[1][0][0]
        attestation = self.get_attestation(self.repository, chunk.code_hash)
        self.assertIsNone(attestation)

        comment = "This is a comment"
        response = self.post_attestation(
            self.repository,
            chunk.code_hash,
            CodeGenerationLabelChoices.BLENDED,
            comment,
        )
        self.assertEqual(response.status_code, 201)

        attestation = self.get_attestation(self.repository, chunk.code_hash)
        self.assertEqual(attestation.label, CodeGenerationLabelChoices.BLENDED)
        self.assertEqual(attestation.comment, comment)

        mock_recalculate_composition.assert_called_once()

    @patch("api.tasks.RecalculateCommitAICompositionTask.run", return_value=({}, set()))
    def test_update_same_label(self, mock_recalculate_composition):
        self.login()

        chunk = self.commit_file_chunks[1][0][0]
        attestation = RepositoryCodeAttestation.objects.create(
            repository=self.repository,
            code_hash=chunk.code_hash,
            label=CodeGenerationLabelChoices.AI,
        )

        response = self.post_attestation(self.repository, chunk.code_hash, CodeGenerationLabelChoices.AI)
        self.assertEqual(response.status_code, 200)

        attestation.refresh_from_db()
        self.assertEqual(attestation.label, CodeGenerationLabelChoices.AI)

        mock_recalculate_composition.assert_called_once()

    @patch("api.tasks.RecalculateCommitAICompositionTask.run", return_value=({}, set()))
    def test_update_different_label(self, mock_recalculate_composition):
        self.login()

        chunk = self.commit_file_chunks[1][0][0]
        attestation = RepositoryCodeAttestation.objects.create(
            repository=self.repository,
            code_hash=chunk.code_hash,
            label=CodeGenerationLabelChoices.AI,
        )

        response = self.post_attestation(
            self.repository,
            chunk.code_hash,
            CodeGenerationLabelChoices.BLENDED,
        )
        self.assertEqual(response.status_code, 200)

        attestation.refresh_from_db()
        self.assertEqual(attestation.label, CodeGenerationLabelChoices.BLENDED)

        mock_recalculate_composition.assert_called_once()

    @patch("api.tasks.RecalculateCommitAICompositionTask.run", return_value=({}, set()))
    def test_update_revert_label(self, mock_recalculate_composition):
        self.login()

        chunk = self.commit_file_chunks[1][0][0]
        attestation = RepositoryCodeAttestation.objects.create(
            repository=self.repository,
            code_hash=chunk.code_hash,
            label=CodeGenerationLabelChoices.AI,
        )

        response = self.post_attestation(
            self.repository,
            chunk.code_hash,
            chunk.code_generation_label,
        )
        self.assertEqual(response.status_code, 200)

        attestation.refresh_from_db()
        self.assertEqual(attestation.label, chunk.code_generation_label)

        mock_recalculate_composition.assert_called_once()

    @parameterized.expand(
        [
            (0, CodeGenerationLabelChoices.AI),
            (0, CodeGenerationLabelChoices.BLENDED),
            (1, CodeGenerationLabelChoices.HUMAN),
            (1, CodeGenerationLabelChoices.BLENDED),
            (2, CodeGenerationLabelChoices.HUMAN),
            (2, CodeGenerationLabelChoices.AI),
        ]
    )
    @patch("mvp.tasks.ImportAIEngineDataTask.load_metadata")
    @patch("api.tasks.RecalculateCommitAICompositionTask.update_organization_background")
    def test_composition_update_unique_chunk(
        self,
        chunk_index,
        attest_label,
        mock_update_organization_background,
        mock_load_metadata,
    ):
        self.login()

        mock_load_metadata.return_value = self.pr_metadata

        chunks = self.get_commit_files_chunks(self.commit_file_chunks[1])

        # the chunk is unique
        chunk = chunks[chunk_index]
        chunk.code_hash = "unique_hash"
        chunk.save()

        self.set_chunk_label(chunk, attest_label)
        expected_ai_fields = self.calculate_chunks_ai_composition(chunks)

        self.post_attestation(self.repository, chunk.code_hash, attest_label)

        self.repository.refresh_from_db()
        self.pr.refresh_from_db()
        self.commits[0].refresh_from_db()
        self.commits[1].refresh_from_db()

        repo_ai_fields = self.get_instance_ai_fields(self.repository)
        pr_ai_fields = self.get_instance_ai_fields(self.pr)
        commit0_ai_fields = self.get_instance_ai_fields(self.commits[0])
        commit1_ai_fields = self.get_instance_ai_fields(self.commits[1])

        # PR & head commit have only the percentages of the modified files
        self.assert_ai_fields_equal(pr_ai_fields, expected_ai_fields)
        self.assert_ai_fields_equal(commit1_ai_fields, expected_ai_fields)

        # no change in base commit or repository
        self.assert_ai_fields_equal(commit0_ai_fields, self.commit_original_ai_fields[0])
        self.assert_ai_fields_equal(repo_ai_fields, self.commit_original_ai_fields[0])
        mock_update_organization_background.assert_not_called()

    @parameterized.expand(
        [
            (0, CodeGenerationLabelChoices.AI),
            (0, CodeGenerationLabelChoices.BLENDED),
            (1, CodeGenerationLabelChoices.HUMAN),
            (1, CodeGenerationLabelChoices.BLENDED),
            (2, CodeGenerationLabelChoices.HUMAN),
            (2, CodeGenerationLabelChoices.AI),
        ]
    )
    @patch("mvp.tasks.ImportAIEngineDataTask.load_metadata")
    @patch("api.tasks.RecalculateCommitAICompositionTask.update_organization_background")
    def test_composition_update_non_unique_chunk(
        self,
        chunk_index,
        attest_label,
        mock_update_organization_background,
        mock_load_metadata,
    ):
        self.login()

        chunks = self.get_commit_files_chunks(self.commit_file_chunks[1])

        # the chunk exists in other commits that are non related to this PR
        chunk = chunks[chunk_index]
        chunk.code_hash = "non_unique_hash"
        chunk.save()

        (
            other_repository,
            other_commits,
            other_pr,
            other_commit_file_chunks,
            other_pr_metadata,
            other_commit_original_ai_fields,
        ) = self.create_repository_data(self.organization, "other")

        other_chunks = self.get_commit_files_chunks(other_commit_file_chunks[1])
        other_chunk = other_chunks[chunk_index]
        other_chunk.code_hash = chunk.code_hash
        other_chunk.save()

        def load_metadata_side_effect(*args, **kwargs):
            if args[0] in other_commits:
                return other_pr_metadata
            else:
                return self.pr_metadata

        mock_load_metadata.side_effect = load_metadata_side_effect

        self.set_chunk_label(chunk, attest_label)
        self.set_chunk_label(other_chunk, attest_label)

        expected_ai_fields = self.calculate_chunks_ai_composition(chunks)
        other_expected_ai_fields = self.calculate_chunks_ai_composition(other_chunks)

        self.post_attestation(self.repository, chunk.code_hash, attest_label)

        self.repository.refresh_from_db()
        self.pr.refresh_from_db()
        self.commits[0].refresh_from_db()
        self.commits[1].refresh_from_db()

        other_repository.refresh_from_db()
        other_pr.refresh_from_db()
        other_commits[0].refresh_from_db()
        other_commits[1].refresh_from_db()

        repo_ai_fields = self.get_instance_ai_fields(self.repository)
        pr_ai_fields = self.get_instance_ai_fields(self.pr)
        commit0_ai_fields = self.get_instance_ai_fields(self.commits[0])
        commit1_ai_fields = self.get_instance_ai_fields(self.commits[1])

        other_repo_ai_fields = self.get_instance_ai_fields(other_repository)
        other_pr_ai_fields = self.get_instance_ai_fields(other_pr)
        other_commit0_ai_fields = self.get_instance_ai_fields(other_commits[0])
        other_commit1_ai_fields = self.get_instance_ai_fields(other_commits[1])

        # PR & head commit have only the percentages of the modified files
        self.assert_ai_fields_equal(pr_ai_fields, expected_ai_fields)
        self.assert_ai_fields_equal(commit1_ai_fields, expected_ai_fields)
        self.assert_ai_fields_equal(other_pr_ai_fields, other_expected_ai_fields)
        self.assert_ai_fields_equal(other_commit1_ai_fields, other_expected_ai_fields)

        # no change in base commit or repository
        self.assert_ai_fields_equal(commit0_ai_fields, self.commit_original_ai_fields[0])
        self.assert_ai_fields_equal(repo_ai_fields, self.commit_original_ai_fields[0])
        self.assert_ai_fields_equal(other_commit0_ai_fields, other_commit_original_ai_fields[0])
        self.assert_ai_fields_equal(other_repo_ai_fields, other_commit_original_ai_fields[0])
        mock_update_organization_background.assert_not_called()

    @parameterized.expand(
        [
            (0, CodeGenerationLabelChoices.AI),
            (0, CodeGenerationLabelChoices.BLENDED),
            (1, CodeGenerationLabelChoices.HUMAN),
            (1, CodeGenerationLabelChoices.BLENDED),
            (2, CodeGenerationLabelChoices.HUMAN),
            (2, CodeGenerationLabelChoices.AI),
        ]
    )
    @patch("mvp.tasks.ImportAIEngineDataTask.load_metadata")
    @patch("api.tasks.RecalculateCommitAICompositionTask.update_organization_background")
    def test_composition_update_shared_chunk(
        self,
        chunk_index,
        attest_label,
        mock_update_organization_background,
        mock_load_metadata,
    ):
        self.login()

        mock_load_metadata.return_value = self.pr_metadata

        chunks0 = self.get_commit_files_chunks(self.commit_file_chunks[0])
        chunks1 = self.get_commit_files_chunks(self.commit_file_chunks[1])

        # the chunk exists in base commit as well (keep the same code hash)
        chunk0 = chunks0[chunk_index]
        chunk1 = chunks1[chunk_index]

        self.set_chunk_label(chunk0, attest_label)
        self.set_chunk_label(chunk1, attest_label)

        expected_ai_fields0 = self.calculate_chunks_ai_composition(chunks0)
        expected_ai_fields1 = self.calculate_chunks_ai_composition(chunks1)

        self.post_attestation(self.repository, chunk1.code_hash, attest_label)

        self.repository.refresh_from_db()
        self.pr.refresh_from_db()
        self.commits[0].refresh_from_db()
        self.commits[1].refresh_from_db()

        repo_ai_fields = self.get_instance_ai_fields(self.repository)
        pr_ai_fields = self.get_instance_ai_fields(self.pr)
        commit0_ai_fields = self.get_instance_ai_fields(self.commits[0])
        commit1_ai_fields = self.get_instance_ai_fields(self.commits[1])

        # PR & head commit have only the percentages of the modified files
        self.assert_ai_fields_equal(pr_ai_fields, expected_ai_fields1)
        self.assert_ai_fields_equal(commit1_ai_fields, expected_ai_fields1)

        # base commit and repository changed, since they share a chunk
        self.assert_ai_fields_equal(commit0_ai_fields, expected_ai_fields0)
        self.assert_ai_fields_equal(repo_ai_fields, expected_ai_fields0)
        mock_update_organization_background.assert_called_once()

    @parameterized.expand(
        [
            (0, CodeGenerationLabelChoices.AI),
            (0, CodeGenerationLabelChoices.BLENDED),
            (1, CodeGenerationLabelChoices.HUMAN),
            (1, CodeGenerationLabelChoices.BLENDED),
            (2, CodeGenerationLabelChoices.HUMAN),
            (2, CodeGenerationLabelChoices.AI),
        ]
    )
    @patch("mvp.tasks.ImportAIEngineDataTask.load_metadata")
    @patch("api.tasks.RecalculateCommitAICompositionTask.update_organization_background")
    def test_composition_update_revert_label(
        self,
        chunk_index,
        attest_label,
        mock_update_organization_background,
        mock_load_metadata,
    ):
        self.login()

        mock_load_metadata.return_value = self.pr_metadata

        # the chunk is unique
        chunk = self.commit_file_chunks[1][0][chunk_index]
        chunk.code_hash = "unique_hash"
        chunk.save()

        original_label = chunk.code_generation_label

        repo_ai_fields_original = self.get_instance_ai_fields(self.repository)
        pr_ai_fields_original = self.get_instance_ai_fields(self.pr)
        commit0_ai_fields_original = self.get_instance_ai_fields(self.commits[0])
        commit1_ai_fields_original = self.get_instance_ai_fields(self.commits[1])

        self.post_attestation(self.repository, chunk.code_hash, attest_label)
        self.post_attestation(self.repository, chunk.code_hash, original_label)

        self.repository.refresh_from_db()
        self.pr.refresh_from_db()
        self.commits[0].refresh_from_db()
        self.commits[1].refresh_from_db()

        repo_ai_fields = self.get_instance_ai_fields(self.repository)
        pr_ai_fields = self.get_instance_ai_fields(self.pr)
        commit0_ai_fields = self.get_instance_ai_fields(self.commits[0])
        commit1_ai_fields = self.get_instance_ai_fields(self.commits[1])

        # everything remains the same
        self.assert_ai_fields_equal(repo_ai_fields, repo_ai_fields_original)
        self.assert_ai_fields_equal(pr_ai_fields, pr_ai_fields_original)
        self.assert_ai_fields_equal(commit0_ai_fields, commit0_ai_fields_original)
        self.assert_ai_fields_equal(commit1_ai_fields, commit1_ai_fields_original)
        mock_update_organization_background.assert_not_called()

    def post_agree_all_attestations(self, repository, payload):
        return self.client.post(
            reverse("attestation-agree_all", kwargs={"pk_encoded": repository.public_id()}),
            payload,
            content_type="application/json",
        )

    @patch("api.tasks.RecalculateCommitAICompositionTask.run", return_value=({}, set()))
    def test_agree_all(self, mock_recalculate_composition):
        self.login()

        chunk_1 = self.commit_file_chunks[0][0][0]
        attestation_1 = self.get_attestation(self.repository, chunk_1.code_hash)
        self.assertIsNone(attestation_1)

        chunk_2 = self.commit_file_chunks[0][0][1]
        attestation_2 = self.get_attestation(self.repository, chunk_2.code_hash)
        self.assertIsNone(attestation_2)

        chunk_3 = self.commit_file_chunks[0][0][2]
        attestation_3 = self.get_attestation(self.repository, chunk_3.code_hash)
        self.assertIsNone(attestation_3)

        pay_load = [
            {
                "code_hash": chunk_1.code_hash,
                "label": CodeGenerationLabelChoices.BLENDED,
            },
            {
                "code_hash": chunk_2.code_hash,
                "label": CodeGenerationLabelChoices.AI,
            },
            {
                "code_hash": chunk_3.code_hash,
                "label": CodeGenerationLabelChoices.HUMAN,
            },
        ]
        response = self.post_agree_all_attestations(
            self.repository,
            pay_load,
        )
        self.assertEqual(response.status_code, 200)

        chunk_1.refresh_from_db()
        attestation_1 = self.get_attestation(self.repository, chunk_1.code_hash)
        self.assertEqual(chunk_1.attestation, attestation_1)
        self.assertTrue(pay_load[0]["label"] == attestation_1.label == chunk_1.get_label())

        chunk_2.refresh_from_db()
        attestation_2 = self.get_attestation(self.repository, chunk_2.code_hash)
        self.assertEqual(chunk_2.attestation, attestation_2)
        self.assertTrue(pay_load[1]["label"] == attestation_2.label == chunk_2.get_label())

        chunk_3.refresh_from_db()
        attestation_3 = self.get_attestation(self.repository, chunk_3.code_hash)
        self.assertEqual(chunk_3.attestation, attestation_3)
        self.assertTrue(pay_load[2]["label"] == attestation_3.label == chunk_3.get_label())

        mock_recalculate_composition.assert_called_once()
