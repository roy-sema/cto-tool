import asyncio
import logging

from otel_extensions import instrumented

from contextualization.pipelines.pipeline_A_automated_process.models import (
    CommitCollection,
)
from contextualization.pipelines.pipeline_A_automated_process.prompts.prompt import (
    DiffAnalyzer,
    diff_analyser_chain,
    diff_analyser_chain_big_text,
)
from contextualization.tools.llm_tools import run_async_batch, separate_big_inputs

logger = logging.getLogger(__name__)


@instrumented
async def analyze_code_changes_collection(commit_diffs_data: CommitCollection) -> CommitCollection:
    only_not_analysed_diffs = commit_diffs_data.only_not_analyzed()
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
            commit.category = str(result.category.value)
            commit.category_justification = result.category_justification
            commit.Purpose_of_change = result.Purpose_of_change
            commit.Impact_on_product = result.Impact_on_product

    return commit_diffs_data


async def analyze_git_diffs_collection(git_diffs: CommitCollection) -> list[DiffAnalyzer]:
    inputs = [
        {
            "diff": row.code,
            "title": row.commit_title,
            "description": row.commit_description,
        }
        for row in git_diffs.commits
    ]
    tasks = []
    small_inputs, big_inputs = await separate_big_inputs(inputs)
    if small_inputs:
        tasks.append(diff_analyser_chain.abatch(small_inputs))

    if big_inputs:
        tasks.append(run_async_batch(diff_analyser_chain_big_text, big_inputs))

    outputs = await asyncio.gather(*tasks, return_exceptions=True)
    outputs = [item for sublist in outputs for item in sublist]

    errors = [item for item in outputs if item is None or isinstance(item, Exception)]
    if len(errors) > 0:
        logger.exception("Exception during analysing git diffs", extra={"errors": errors})

    return [item for item in outputs if item is not None and not isinstance(item, Exception)]
