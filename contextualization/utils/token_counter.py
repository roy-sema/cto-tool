import logging
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
model = os.getenv("MODEL")

client = anthropic.Anthropic(api_key=api_key)


def get_token_count_anthropic(input_text):
    response = client.beta.messages.count_tokens(model=model, messages=[{"role": "user", "content": f"{input_text}"}])
    logging.info(f"Input tokens: {response.input_tokens}")
    return response.input_tokens


with open("/Users/adeepak7/Documents/study/sema_repos/contextualization/commit_data.json", "r") as json_file:
    file_contents = json_file.read()

    get_token_count_anthropic(file_contents)
