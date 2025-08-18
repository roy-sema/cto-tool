import asyncio
import logging

from otel_extensions import instrumented

from contextualization.pipelines.pipeline_A_automated_process.models import CommitCollection
from contextualization.pipelines.pipeline_A_automated_process.prompts.prompt import (
    DevActivityCategories,
    DiffAnalyzer,
    diff_analyser_chain,
    diff_analyser_chain_big_text,
)
from contextualization.tools.llm_tools import run_async_batch, separate_big_inputs


@instrumented
async def analyze_code_changes_collection(commit_diffs_data: CommitCollection) -> CommitCollection:
    only_not_analysed_diffs = commit_diffs_data.filter_analyzed()
    if only_not_analysed_diffs.is_empty():
        return commit_diffs_data

    results = await analyze_git_diffs_collection(only_not_analysed_diffs)
    if not results:
        return commit_diffs_data

    # Update commits with analysis results
    for i, result in enumerate(results):
        if i > len(only_not_analysed_diffs.commits):
            continue

        commit_id = only_not_analysed_diffs.commits[i].id
        for commit in commit_diffs_data.commits:
            if commit.id != commit_id:
                continue

            commit.Summary = result.Summary
            commit.Categorization_of_Changes = get_dev_activity_categories_from_json(result.Categorization_of_Changes)
            commit.Maintenance_Relevance = result.Maintenance_Relevance
            commit.Description_of_Maintenance_Relevance = result.Description_of_Maintenance_Relevance
            commit.Purpose_of_change = result.Purpose_of_change
            commit.Impact_on_product = result.Impact_on_product

    return commit_diffs_data


async def analyze_git_diffs_collection(git_diffs: CommitCollection) -> list[DiffAnalyzer]:
    results = []
    try:
        git_data = git_diffs.to_records()
        inputs = [
            {
                "diff": row["code"],
                "title": row["commit_title"],
                "description": row["commit_description"],
            }
            for row in git_data
        ]
        tasks = []
        small_inputs, big_inputs = await separate_big_inputs(inputs)
        if small_inputs:
            tasks.append(diff_analyser_chain.abatch(small_inputs))

        if big_inputs:
            tasks.append(run_async_batch(diff_analyser_chain_big_text, big_inputs))

        outputs = await asyncio.gather(*tasks, return_exceptions=True)
        outputs = [item for sublist in outputs for item in sublist if not isinstance(item, Exception)]
        for output in outputs:
            results.append(output)
        return results
    except Exception:
        logging.exception("Pipeline A - Error processing batch")
        return []


def filter_analysed_diffs_collection(git_diffs: CommitCollection) -> CommitCollection:
    if git_diffs.is_empty():
        return git_diffs

    filtered_commits = [commit for commit in git_diffs.commits if commit.Summary is None]
    return CommitCollection(commits=filtered_commits)


def get_dev_activity_categories_from_json(categories: DevActivityCategories) -> str:
    if isinstance(categories, str):
        return categories
    return ", ".join(field.replace("_", " ").capitalize() for field, value in categories.model_dump().items() if value)
