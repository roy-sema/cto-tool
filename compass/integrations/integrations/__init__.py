# F401 is a ruff rule that the import is not used

import logging

from .azure_devops_integration import (  # noqa: F401
    AzureDevOpsIntegration,
    AzureDevOpsPullRequestData,
)
from .base_integration import BaseIntegration  # noqa: F401
from .bitbucket_integration import (  # noqa: F401
    BitBucketIntegration,
    BitBucketPullRequestData,
)
from .codacy_integration import CodacyIntegration, CodacyIssueCategory  # noqa: F401
from .git_base_integration import (  # noqa: F401
    CheckRunStatus,
    GitBaseIntegration,
    GitCommitData,
    GitRepositoryData,
    GitServerBusyException,
    GitServerDisconnectException,
    PullRequestData,
)
from .github_integration import GitHubIntegration, GitHubPullRequestData  # noqa: F401
from .integration_factory import IntegrationFactory  # noqa: F401
from .iradar_integration import (  # noqa: F401
    IRadarIntegration,
    IRadarIssueSeverity,
    IRadarIssueType,
)
from .jira_integration import JiraIntegration  # noqa: F401
from .mailchimp_integration import MailChimpIntegration  # noqa: F401
from .slack_integration import SlackIntegration  # noqa: F401
from .snyk_integration import (  # noqa: F401
    SnykIntegration,
    SnykIssueSeverity,
    SnykIssueType,
    SnykLicenseSeverity,
)

logger = logging.getLogger(__name__)

CODEBASE_REPORT_INTEGRATIONS = [
    AzureDevOpsIntegration,
    BitBucketIntegration,
    CodacyIntegration,
    GitHubIntegration,
    IRadarIntegration,
    SnykIntegration,
]

# TODO: add GitLab when implemented
GIT_INTEGRATIONS = [AzureDevOpsIntegration, BitBucketIntegration, GitHubIntegration]


def get_codebase_reports_providers():
    return [integration().provider for integration in CODEBASE_REPORT_INTEGRATIONS]


def get_git_providers():
    return [integration().provider for integration in GIT_INTEGRATIONS]


def get_git_integrations_by_provider():
    return {integration().provider: integration for integration in GIT_INTEGRATIONS}


def get_git_provider_integration(provider):
    integration = get_git_integrations_by_provider().get(provider)

    if not integration:
        logger.warning(f"Provider {provider} is not a supported Git provider")
        return None

    return integration
