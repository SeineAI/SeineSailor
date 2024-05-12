import logging
import os
import asyncio
from options import Options, LLMOptions
from logger import setup_logger


async def main():
    options = Options(
        debug=os.environ.get("INPUT_DEBUG", False),
        disable_review=os.environ.get("INPUT_DISABLE_REVIEW", False),
        disable_release_notes=os.environ.get("INPUT_DISABLE_RELEASE_NOTES", False),
        max_files=os.environ.get("INPUT_MAX_FILES", "0"),
        review_simple_changes=os.environ.get("INPUT_REVIEW_SIMPLE_CHANGES", False),
        review_comment_lgtm=os.environ.get("INPUT_REVIEW_COMMENT_LGTM", False),
        path_filters=os.environ.get("INPUT_PATH_FILTERS", "").split("\n") if os.environ.get(
            "INPUT_PATH_FILTERS") else None,
        system_message=os.environ.get("INPUT_SYSTEM_MESSAGE", ""),
        llm_light_model=os.environ.get("INPUT_LLM_LIGHT_MODEL", "mistralai/mixtral-8x7b-instruct-v01"),
        llm_heavy_model=os.environ.get("INPUT_LLM_HEAVY_MODEL", "meta-llama/llama-3-70b-instruct"),
        llm_model_temperature=os.environ.get("INPUT_LLM_MODEL_TEMPERATURE", "0.0"),
        llm_retries=os.environ.get("INPUT_LLM_RETRIES", "3"),
        llm_timeout_ms=os.environ.get("INPUT_LLM_TIMEOUT_MS", "120000"),
        llm_concurrency_limit=os.environ.get("INPUT_LLM_CONCURRENCY_LIMIT", "6"),
        github_concurrency_limit=os.environ.get("INPUT_GITHUB_CONCURRENCY_LIMIT", "6"),
        api_base_url=os.environ.get("INPUT_LLM_BASE_URL", "https://us-south.ml.cloud.ibm.com"),
        language=os.environ.get("INPUT_LANGUAGE", "en-US"),
        api_type=os.environ.get("INPUT_LLM_API_TYPE", "watsonx")
    )

    if options.debug:
        os.environ["SEINE_SAILOR_LOG_LEVEL"] = str(logging.DEBUG)
        options.print()

    logger = setup_logger("main")

    from prompts import Prompts
    from bot import Bot
    from review import code_review
    from review_comment import handle_review_comment

    prompts = Prompts(
        summarize=os.environ.get("INPUT_SUMMARIZE", ""),
        summarize_release_notes=os.environ.get("INPUT_SUMMARIZE_RELEASE_NOTES", "")
    )

    try:
        light_bot = Bot(options, LLMOptions(options.llm_light_model, options.light_token_limits))
    except Exception as e:
        print(f"Skipped: failed to create summary bot, please check your openai_api_key: {e}")
        return

    try:
        heavy_bot = Bot(options, LLMOptions(options.llm_heavy_model, options.heavy_token_limits))
    except Exception as e:
        print(f"Skipped: failed to create review bot, please check your openai_api_key: {e}")
        return

    logger.debug(f"GITHUB_EVENT_NAME:{os.environ.get('GITHUB_EVENT_NAME')}")

    try:
        if os.environ.get("GITHUB_EVENT_NAME") in ["pull_request", "pull_request_target"]:
            await code_review(light_bot, heavy_bot, options, prompts)
        elif os.environ.get("GITHUB_EVENT_NAME") == "pull_request_review_comment":
            await handle_review_comment(heavy_bot, options, prompts)
        else:
            print("Skipped: this action only works on push events or pull_request")
    except Exception as e:
        print(f"Failed to run: {e}")


if __name__ == "__main__":
    asyncio.run(main())
