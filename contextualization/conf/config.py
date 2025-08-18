import dataclasses
import os

import yaml
from dotenv import load_dotenv

root_dir = os.path.abspath(os.path.dirname(__file__))

load_dotenv()

llm_name = os.getenv("LLM", "claude")
config_file = os.getenv("CONFIG_FILE", "config.yaml")
yaml_path = os.path.join(root_dir, config_file)
with open(yaml_path) as f:
    conf = yaml.safe_load(f)


@dataclasses.dataclass
class LLMConfig:
    name: str
    model: str
    temperature: float
    token_limit: float
    batch_threshold: float
    request_per_second: float


def get_config(big_text: bool = False) -> LLMConfig:
    llm = conf["llms"]["default_llm"]
    if big_text:
        llm = conf["llms"]["big_text_llm"]
    llm_conf = conf["llms"][llm]

    # override for mocked runs
    requests_per_second = int(os.getenv("REQUESTS_PER_SECOND", llm_conf["requests_per_second"]))

    return LLMConfig(
        name=llm,
        model=llm_conf["model"],
        temperature=llm_conf["temperature"],
        token_limit=llm_conf["token_limit"],
        batch_threshold=llm_conf["batch_threshold"],
        request_per_second=requests_per_second,
    )
