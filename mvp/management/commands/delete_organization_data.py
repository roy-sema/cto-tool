import logging
import os.path

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from compass.contextualization.models import DailyMessage
from compass.dashboard.models import GitDiffRepositoryGroupInsight
from compass.integrations.integrations import get_git_provider_integration
from mvp.models import (
    Author,
    AuthorGroup,
    DataProviderConnection,
    DataProviderMember,
    DataProviderProject,
    Organization,
    Repository,
    RepositoryGroup,
    Rule,
    ScoreRecord,
)
from mvp.utils import shred_path

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Deletes given organization data from the database and all associated files from disk,
    does NOT delete the organization instance itself unless --remove-organization flag is set.
    if no orgid is set then it will process organizations with `marked_for_deletion` flag set to true
    """

    def add_arguments(self, parser):
        parser.add_argument("--orgid", type=int, help="ID of the organization to delete.")

        parser.add_argument(
            "--code-only",
            action="store_true",
            help="Deletes only the code from the disk, leaving database records intact.",
        )

        parser.add_argument(
            "--no-input",
            action="store_true",
            help="no confirmation is required.",
        )

        parser.add_argument(
            "--delete-organization",
            action="store_true",
            help="also remove the organization instance",
        )

    def handle(self, *args, **options):
        org_id = options.get("orgid")
        code_only = options.get("code_only", False)
        no_input = options.get("no_input", False)
        delete_organization = options.get("delete_organization", False)

        if no_input and org_id:
            raise CommandError("--no-input is not supported when running for individual organizations.")

        if code_only and delete_organization:
            raise CommandError("Cannot specify both --code-only and --delete-organization")

        organizations = (
            Organization.objects.filter(id=org_id, marked_for_deletion=True)
            if org_id
            else Organization.objects.filter(marked_for_deletion=True)
        )
        if not organizations.exists():
            if org_id:
                logger.error(
                    f"No such organization found or organization is not marked for deletion",
                    extra={"organization_id": org_id},
                )

            else:
                logger.info("No organizations marked for deletion")
            return

        if not no_input:
            logger.info("Confirm you want to:")
            logger.info("  - Delete code from disk")

            if not code_only:
                logger.info("  - Delete data from database")
                logger.info("  - Disconnect from data providers such as GitHub")
            if delete_organization:
                logger.info("  - Delete organization")

        if org_id:
            org = organizations.first()
            if not no_input:
                logger.info(f"Organization: '{org.name}'")
                confirmation = input(f"Are you sure you want to continue? (y/n): ")
                if confirmation.lower() != "y":
                    logger.info("Deletion aborted")
                    return

                org_name_input = input(f"Type the name of the organization to delete ({org.name}): ")
                if org_name_input != org.name:
                    logger.info("Organization name does not match. Deletion aborted")
                    return
        else:
            if not no_input:
                logger.info(f"Attempting to delete the following organizations [{len(organizations)}]")
                for org in organizations:
                    logger.info(f"  - Organization: '{org.name}'")
                confirmation = input(f"Are you sure you want to continue? (y/n): ")
                if confirmation.lower() != "y":
                    logger.info("Deletion aborted")
                    return

        for org in organizations:
            try:
                self.process_organization(org, code_only, delete_organization)
            except Exception:
                logger.exception(
                    "Failed to delete organization",
                    extra={
                        "organization": org.name,
                        "organization_public_id": org.public_id(),
                    },
                )

    def process_organization(self, organization, code_only, delete_organization=False):
        logger.info(f"Processing organization: {organization.name}")

        if not code_only:
            # disconnecting first so that if the deletion fails, no more data will be downloaded anyway
            logger.info(f"Disconnecting from data providers")
            for connection in organization.dataproviderconnection_set.all():
                integration = get_git_provider_integration(connection.provider)
                if not integration:
                    continue

                logger.info(f"Disconnecting from {connection.provider}")
                integration.disconnect(connection)

        logger.info("Deleting repository data from disk")
        org_full_scan_path = organization.get_download_directory()
        self.delete_path(org_full_scan_path)

        logger.info("Deleting PR data from disk")
        org_pr_path = organization.get_download_directory(is_pull_request=True)
        self.delete_path(org_pr_path)

        if code_only:
            logger.info("Code deleted successfully")
            return

        logger.info("Deleting data from database")
        self.delete_object(Author, organization=organization)
        self.delete_object(AuthorGroup, organization=organization)
        self.delete_object(DataProviderConnection, organization=organization)
        self.delete_object(DataProviderMember, organization=organization)
        self.delete_object(DataProviderProject, organization=organization)
        self.delete_object(ScoreRecord, organization=organization)
        self.delete_object(DailyMessage, organization=organization)
        self.delete_object_loop(Repository, organization=organization)
        self.delete_object(RepositoryGroup, organization=organization)
        self.delete_object(Rule, organization=organization)
        self.delete_object(GitDiffRepositoryGroupInsight, organization=organization)

        logger.info("Clearing geographies")
        organization.geographies.clear()

        logger.info(f"Organization {organization.name} data deleted successfully")
        if delete_organization:
            organization.delete()
            logger.info(f"Organization {organization.name} deleted successfully")
        else:
            organization.marked_for_deletion = False
            organization.save()

    def delete_path(self, path):
        """
        Recursively delete a directory and its contents, uses `rm`
        """

        if not os.path.exists(path):
            logger.info(f"Path {path} does not exist, skipping deletion")
            return

        try:
            shred_path(path)
        except Exception:
            logger.exception("Error: failed to delete organization data")
            raise

    def delete_object(self, model, **filters):
        if not filters:
            raise ValueError("No filters provided. At least one filter is required.")
        objects = model.objects.filter(**filters)

        logger.info(f"Deleting {len(objects)} {model.__name__}")
        objects.delete()

    def delete_object_loop(self, model, **filters):
        # This method is used to delete objects in a loop, which is useful for large datasets or deeply cascaded deletions.
        if not filters:
            raise ValueError("No filters provided. At least one filter is required.")

        pks = model.objects.filter(**filters).values_list("id", flat=True)

        logger.info(f"Deleting {len(pks)} {model.__name__}")

        for pk in pks:
            model.objects.filter(id=pk).delete()
