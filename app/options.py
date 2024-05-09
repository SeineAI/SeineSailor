import os
from typing import List
from fnmatch import fnmatch
from logger import setup_logger
from limits import TokenLimits

logger = setup_logger("options")

class PathFilter:
    def __init__(self, rules: List[str] = None):
        self.rules = []
        if rules:
            for rule in rules:
                trimmed = rule.strip()
                if trimmed:
                    if trimmed.startswith("!"):
                        self.rules.append((trimmed[1:].strip(), True))
                    else:
                        self.rules.append((trimmed, False))

    def check(self, path: str) -> bool:
        if not self.rules:
            return True

        included = False
        excluded = False
        inclusion_rule_exists = False

        for rule, exclude in self.rules:
            if fnmatch(path, rule):
                if exclude:
                    excluded = True
                else:
                    included = True

            if not exclude:
                inclusion_rule_exists = True

        return (not inclusion_rule_exists or included) and not excluded

class LLMOptions:
    def __init__(self, model: str = "mistralai/mixtral-8x7b-instruct-v01", token_limits: "TokenLimits" = None):
        self.model = model
        self.token_limits = token_limits if token_limits else TokenLimits(model)

class Options:
    def __init__(
        self,
        debug: bool,
        disable_review: bool,
        disable_release_notes: bool,
        max_files: str = "0",
        review_simple_changes: bool = False,
        review_comment_lgtm: bool = False,
        path_filters: List[str] = None,
        system_message: str = "",
        llm_light_model: str = "mistralai/mixtral-8x7b-instruct-v01",
        llm_heavy_model: str = "meta-llama/llama-3-70b-instruct",
        llm_model_temperature: str = "0.0",
        llm_retries: str = "3",
        llm_timeout_ms: str = "120000",
        llm_concurrency_limit: str = "6",
        github_concurrency_limit: str = "6",
        api_base_url: str = "https://us-south.ml.cloud.ibm.com",
        language: str = "en-US",
        api_type: str = "watsonx"
    ):
        self.debug = debug
        self.disable_review = disable_review
        self.disable_release_notes = disable_release_notes
        self.max_files = int(max_files)
        self.review_simple_changes = review_simple_changes
        self.review_comment_lgtm = review_comment_lgtm
        self.path_filters = PathFilter(path_filters)
        self.system_message = system_message
        self.llm_light_model = llm_light_model
        self.llm_heavy_model = llm_heavy_model
        self.llm_model_temperature = float(llm_model_temperature)
        self.llm_retries = int(llm_retries)
        self.llm_timeout_ms = int(llm_timeout_ms)
        self.llm_concurrency_limit = int(llm_concurrency_limit)
        self.github_concurrency_limit = int(github_concurrency_limit)
        self.light_token_limits = TokenLimits(llm_light_model)
        self.heavy_token_limits = TokenLimits(llm_heavy_model)
        self.api_base_url = api_base_url
        self.language = language
        self.api_type = api_type

    def print(self):
        logger.info(f"debug: {self.debug}")
        logger.info(f"disable_review: {self.disable_review}")
        logger.info(f"disable_release_notes: {self.disable_release_notes}")
        logger.info(f"max_files: {self.max_files}")
        logger.info(f"review_simple_changes: {self.review_simple_changes}")
        logger.info(f"review_comment_lgtm: {self.review_comment_lgtm}")
        logger.info(f"path_filters: {self.path_filters}")
        logger.info(f"system_message: {self.system_message}")
        logger.info(f"llm_light_model: {self.llm_light_model}")
        logger.info(f"llm_heavy_model: {self.llm_heavy_model}")
        logger.info(f"llm_model_temperature: {self.llm_model_temperature}")
        logger.info(f"llm_retries: {self.llm_retries}")
        logger.info(f"llm_timeout_ms: {self.llm_timeout_ms}")
        logger.info(f"llm_concurrency_limit: {self.llm_concurrency_limit}")
        logger.info(f"github_concurrency_limit: {self.github_concurrency_limit}")
        logger.info(f"summary_token_limits: {self.light_token_limits.string()}")
        logger.info(f"review_token_limits: {self.heavy_token_limits.string()}")
        logger.info(f"api_base_url: {self.api_base_url}")
        logger.info(f"language: {self.language}")

    def check_path(self, path: str) -> bool:
        ok = self.path_filters.check(path)
        logger.info(f"checking path: {path} => {ok}")
        return ok