import os
import time
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ibm import WatsonxLLM

from app.options import Options, LLMOptions
from app.logger import setup_logger

logger = setup_logger("bot")


class Bot:
    def __init__(self, options: Options, llm_options: LLMOptions):
        self.options = options
        self.llm_options = llm_options
        self.api = None
        current_date = datetime.now().strftime("%Y-%m-%d")
        self.system_message = (
            f"{options.system_message}\n"
            f"Knowledge cutoff: {llm_options.token_limits.knowledge_cut_off}\n"
            f"Current date: {current_date}\n\n"
            f"IMPORTANT: Entire response must be in the language with ISO code: {options.language}"
        )
        output_parser = StrOutputParser()

        if options.api_type == "openai":
            if os.environ.get("OPENAI_API_KEY"):
                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_message),
                    HumanMessagePromptTemplate.from_template("{human_input}")
                ])
                llm = ChatOpenAI(
                    openai_api_base=options.api_base_url,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                    openai_organization=os.environ.get("OPENAI_API_ORG", None),
                    max_tokens=llm_options.token_limits.response_tokens,
                    temperature=options.llm_model_temperature,
                    model=llm_options.model
                )
                self.api = prompt | llm | output_parser
            else:
                raise Exception(
                    "Unable to initialize the OpenAI API, the 'OPENAI_API_KEY' environment variable is not available"
                )
        elif options.api_type == "watsonx":
            if os.environ.get("IBM_CLOUD_API_KEY") and os.environ.get("WATSONX_PROJECT_ID"):
                if self.llm_options.model == "mistralai/mixtral-8x7b-instruct-v01":
                    template = f"[INST]{self.system_message}\n\n{{human_input}}[/INST]"
                elif self.llm_options.model == "meta-llama/llama-3-70b-instruct":
                    template = (f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                                f"{self.system_message}<|eot_id|>\n"
                                f"<|start_header_id|>user<|end_header_id|>\n\n"
                                f"{{human_input}}<|eot_id|>\n"
                                f"<|start_header_id|>assistant<|end_header_id|>")
                else:
                    template = f"system_prompt: {self.system_message}\n\nuser_input: {{human_input}}"
                prompt = PromptTemplate.from_template(template)
                llm = WatsonxLLM(
                    model_id=llm_options.model,
                    url=options.api_base_url,
                    apikey=os.environ["IBM_CLOUD_API_KEY"],
                    project_id=os.environ["WATSONX_PROJECT_ID"],
                    params={
                        "max_new_tokens": llm_options.token_limits.response_tokens,
                        "min_new_tokens": 0,
                        "temperature": options.llm_model_temperature,
                    },
                )
                self.api = prompt | llm | output_parser
            else:
                raise Exception(
                    "Unable to initialize WatsonX AI, both 'IBM_CLOUD_API_KEY' and 'WATSONX_PROJECT_ID' "
                    "environment variables are not available"
                )
        else:
            raise Exception(f"{options.api_type} API is not supported")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def chat(self, message: str):
        start = time.time()
        response_text = ""
        try:
            response_text = await self.api.ainvoke({"human_input": message})
        except Exception as e:
            logger.error(f"Failed to send message to {self.options.api_type}: {e}")

        end = time.time()
        logger.info(f"Response: {response_text}\n\nResponse time: {end - start} ms")

        if response_text.startswith("with "):
            response_text = response_text[5:]

        if self.options.debug:
            logger.info(f"{self.options.api_type} responses: {response_text}")

        return response_text


if __name__ == "__main__":
    # test
    import asyncio

    openai_option = Options(True, False, False,
                            llm_light_model="gpt-3.5-turbo", api_type="openai",
                            api_base_url="https://api.openai.com/v1")
    openai_bot = Bot(openai_option, LLMOptions("gpt-3.5-turbo"))
    watsonx_option = Options(True, False, False)
    watsonx_bot = Bot(watsonx_option, LLMOptions("mistralai/mixtral-8x7b-instruct-v01"))


    async def main():
        response = await openai_bot.chat("This is a test. Please generate 'Hello World' and today's date.")
        print(response)


    asyncio.run(main())
