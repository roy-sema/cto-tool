import pandas as pd

from contextualization.conf.config import get_config
from contextualization.tools.llm_tools import count_tokens


async def get_jira_issues_batches(dataframe: pd.DataFrame, prompt_tokens: int = 1500) -> list[str]:
    config = get_config()
    full_prompt_token_limit = 10000 + prompt_tokens

    dataframe["combined"] = dataframe.apply(lambda row: " ".join(map(str, row)), axis=1)

    combined_texts = dataframe["combined"].tolist()
    token_counts = await count_tokens(combined_texts)
    dataframe["combined_token_count"] = token_counts

    text_batches = []
    token_sum = 0
    text_accumulated = ""
    for idx, row in dataframe.iterrows():
        if token_sum >= full_prompt_token_limit:
            text_batches.append(text_accumulated)
            token_sum = 0
            text_accumulated = ""

        text_accumulated = text_accumulated + row["combined"] + "\n"
        token_sum += row["combined_token_count"]

    if text_accumulated:
        text_batches.append(text_accumulated)

    return text_batches
