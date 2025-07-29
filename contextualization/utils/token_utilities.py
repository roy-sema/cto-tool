import tiktoken

model = "gpt-4"
encoding = tiktoken.encoding_for_model(model)


def count_tokens_using_llm_invoke(prompt: str, llm) -> int:
    response = llm.invoke(prompt)
    # logging.info(response.response_metadata)

    response_metadata_dict = dict(response.response_metadata)
    # logging.info(f"Response: {response_metadata_dict['usage']['prompt_tokens']}")

    prompt_tokens = response_metadata_dict["usage"]["prompt_tokens"]

    return prompt_tokens


def count_tokens_using_tiktoken(prompt: str) -> int:
    tokens = encoding.encode(prompt)
    return len(tokens)


def trim_tokens(text, token_limit):
    truncated_tokens = encoding.encode(text)[:token_limit]
    truncated_git_diff_code = encoding.decode(truncated_tokens)
    return truncated_git_diff_code.strip()
