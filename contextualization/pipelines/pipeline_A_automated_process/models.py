from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class CommitData(BaseModel):
    """Model representing a single commit with its metadata and code changes."""

    repository: str
    id: str = Field(description="Commit SHA")
    name: str = Field(description="Commit author name")
    commit_title: str
    commit_description: str
    files: list[str] = Field(default_factory=list, description="List of files changed in the commit")
    branch_name: Optional[str] = None
    date: date
    code: Optional[str] = Field(None, description="Git diff content")
    tik_tokens: Optional[int] = Field(None, description="Token count for the code")

    # Analysis fields (populated during processing)
    Summary: Optional[str] = None
    Categorization_of_Changes: Optional[str] = None
    Maintenance_Relevance: Optional[str] = None
    Description_of_Maintenance_Relevance: Optional[str] = None
    Purpose_of_change: Optional[str] = None
    Impact_on_product: Optional[str] = None


class CommitCollection(BaseModel):
    commits: list[CommitData] = Field(default_factory=list)

    def __len__(self):
        return len(self.commits)

    def filter_by_repos(self, repos: list[str]) -> "CommitCollection":
        filtered_commits = [commit for commit in self.commits if commit.repository in repos]
        return CommitCollection(commits=filtered_commits)

    def filter_analyzed(self) -> "CommitCollection":
        filtered_commits = [commit for commit in self.commits if commit.Summary is None]
        return CommitCollection(commits=filtered_commits)

    def to_records(self) -> list[dict[str, Any]]:
        return [commit.model_dump() for commit in self.commits]

    def is_empty(self) -> bool:
        return len(self.commits) == 0


class CategoryData(BaseModel):
    """Model for category data in analysis results."""

    percentage: float
    justification: str
    examples: str


class AnalysisResults(BaseModel):
    """Model for aggregated analysis results."""

    categories: dict[str, CategoryData]
    summary: str


class RepositoryChangeCount(BaseModel):
    """Model for counting changes per repository and category."""

    repository: str
    category_counts: dict[str, int] = Field(default_factory=dict)
