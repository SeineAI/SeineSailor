import os
from chatgpt import ChatGPTAPI, ChatGPTError, ChatMessage
from langchain.community.llms.watsonx_ai import WatsonxAI
from p_retry import retry
from options import Options, LLMOptions
import time
import datetime
import json

from logger import setup_logger

logger = setup_logger("bot")

class Bot:
    def __init__(self, options: Options, llm_options: LLMOptions):
        self.options = options
        self.llm_options = llm_options
        self.api = None

        if options.api_type == "openai":
            if os.environ.get("OPENAI_API_KEY"):
                current_date = datetime.now().strftime("%Y-%m-%d")
                system_message = f"{options.system_message}\nKnowledge cutoff: {llm_options.token_limits.knowledge_cut_off}\nCurrent date: {current_date}\n\nIMPORTANT: Entire response must be in the language with ISO code: {options.language}"

                self.api = ChatGPTAPI(
                    api_base_url=options.api_base_url,
                    system_message=system_message,
                    api_key=os.environ["OPENAI_API_KEY"],
                    api_org=os.environ.get("OPENAI_API_ORG", None),
                    debug=options.debug,
                    max_model_tokens=llm_options.token_limits.max_tokens,
                    max_response_tokens=llm_options.token_limits.response_tokens,
                    completion_params={
                        "temperature": options.llm_model_temperature,
                        "model": llm_options.model,
                    },
                )
            else:
                raise Exception(
                    "Unable to initialize the OpenAI API, the 'OPENAI_API_KEY' environment variable is not available"
                )
        elif options.api_type == "watsonx":
            if os.environ.get("IBM_CLOUD_API_KEY") and os.environ.get("WATSONX_PROJECT_ID"):
                self.api = WatsonxAI(
                    model_id=llm_options.model,
                    ibm_cloud_api_key=os.environ["IBM_CLOUD_API_KEY"],
                    project_id=os.environ["WATSONX_PROJECT_ID"],
                    model_parameters={
                        "max_new_tokens": llm_options.token_limits.response_tokens,
                        "min_new_tokens": 0,
                        "stop_sequences": [],
                        "repetition_penalty": 1,
                        "temperature": options.llm_model_temperature,
                    },
                )
            else:
                raise Exception(
                    "Unable to initialize WatsonX AI, both 'IBM_CLOUD_API_KEY' and 'WATSONX_PROJECT_ID' environment variables are not available"
                )
        else:
            raise Exception(f"Unsupported API type: {options.api_type}")

    def format_prompt(self, user_message: str) -> str:
        if self.options.api_type == "watsonx":
            current_date = datetime.now().strftime("%Y-%m-%d")
            system_prompt = f"{self.options.system_message}\nKnowledge cutoff: {self.llm_options.token_limits.knowledge_cut_off}\nCurrent date: {current_date}\n\nIMPORTANT: Entire response must be in the language with ISO code: {self.options.language}"
            if self.llm_options.model == "mistralai/mixtral-8x7b-instruct-v01":
                return f"[INST]{system_prompt}\n\n{user_message}[/INST]"
            elif self.llm_options.model == "meta-llama/llama-3-70b-instruct":
                return f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>\n<|start_header_id|>user<|end_header_id|>\n\n{user_message}<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>"

        return user_message

    async def chat(self, message: str, ids: dict) -> tuple[str, dict]:
        try:
            return await self._chat(message, ids)
        except ChatGPTError as e:
            logger.warning(f"Failed to chat: {e}, backtrace: {e.stack}")
            return "", {}

    async def _chat(self, message: str, ids: dict) -> tuple[str, dict]:
        start = time.time()

        if not message:
            return "", {}

        response = None

        if self.api is not None:
            if self.options.api_type == "openai":
                opts = {"timeout_ms": self.options.llm_timeout_ms}
                if ids.get("parent_message_id"):
                    opts["parent_message_id"] = ids["parent_message_id"]
                try:
                    response = await retry(
                        lambda: self.api.send_message(message, opts),
                        retries=self.options.llm_retries,
                    )
                except ChatGPTError as e:
                    logger.info(
                        f"response: {response}, failed to send message to OpenAI: {e}, backtrace: {e.stack}"
                    )
            elif self.options.api_type == "watsonx":
                formatted_prompt = self.format_prompt(message)
                try:
                    response = await retry(
                        lambda: self.api.invoke(formatted_prompt),
                        retries=self.options.llm_retries,
                    )
                except Exception as e:
                    logger.info(
                        f"response: {response}, failed to send message to WatsonX AI: {e}, backtrace: {e.stack}"
                    )

            end = time.time()
            logger.info(f"response: {json.dumps(response)}")
            logger.info(
                f"{self.options.api_type} {'sendMessage' if self.options.api_type == 'openai' else 'invoke'} (including retries) response time: {end - start} ms"
            )
        else:
            raise Exception(f"{self.options.api_type} API is not initialized")

        response_text = ""
        if response is not None:
            if self.options.api_type == "openai":
                response_text = response.text
            elif self.options.api_type == "watsonx":
                response_text = response
        else:
            logger.warning(f"{self.options.api_type} response is null")

        if response_text.startswith("with "):
            response_text = response_text[5:]

        if self.options.debug:
            logger.info(f"{self.options.api_type} responses: {response_text}")

        new_ids = {}
        if self.options.api_type == "openai":
            new_ids["parent_message_id"] = response.id
            new_ids["conversation_id"] = response.conversation_id

        return response_text, new_ids