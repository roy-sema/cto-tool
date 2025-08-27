from datetime import date
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, Field


class CommitData(BaseModel):
    repository: str
    id: str = Field(description="Commit SHA")
    name: str = Field(description="Commit author name")
    commit_title: str
    commit_description: str
    files: list[str] = Field(default_factory=list, description="List of files changed in the commit")
    branch_name: str | None = None
    date: date
    code: str | None = Field(None, description="Git diff content")
    tik_tokens: int | None = Field(None, description="Token count for the code")

    # Analysis fields (populated during processing)
    Summary: str | None = None
    category: str | None = None
    category_justification: str | None = None
    Purpose_of_change: str | None = None
    Impact_on_product: str | None = None


class CommitCollection(BaseModel):
    commits: list[CommitData] = Field(default_factory=list)

    def __len__(self):
        return len(self.commits)

    def filter_by_repos(self, repos: list[str]) -> "CommitCollection":
        filtered_commits = [commit for commit in self.commits if commit.repository in repos]
        return CommitCollection(commits=filtered_commits)

    def only_not_analyzed(self) -> "CommitCollection":
        filtered_commits = [commit for commit in self.commits if commit.Summary is None]
        return CommitCollection(commits=filtered_commits)

    def to_records(self) -> list[dict[str, Any]]:
        return [commit.model_dump() for commit in self.commits]

    def is_empty(self) -> bool:
        return len(self.commits) == 0


class DevelopmentActivityType(StrEnum):
    tech_debt = auto()
    new_feature = auto()
    bug_fix = auto()
    documentation = auto()
    feature_enhancement = auto()
    security = auto()
    testing = auto()
    other = auto()


class DevelopmentActivityJustification(BaseModel):
    activity_type: DevelopmentActivityType = Field(description="Development activity type")
    justification: str = Field(description="Justification summary as per given data.")
