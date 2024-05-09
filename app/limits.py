class TokenLimits:
    def __init__(self, model="gpt-3.5-turbo"):
        self.knowledge_cut_off = "2021-09-01"

        if model == "gpt-4-32k":
            self.max_tokens = 32600
            self.response_tokens = 4000
        elif model == "gpt-3.5-turbo-16k":
            self.max_tokens = 16300
            self.response_tokens = 3000
        elif any(substring in model for substring in ["gpt-4", "mixtral", "llama-3"]):
            self.max_tokens = 8000
            self.response_tokens = 2000
        elif model in ["mistral-tiny", "mistral-small", "mistral-medium"]:
            self.max_tokens = 32000
            self.response_tokens = 4000
        else:
            self.max_tokens = 4000
            self.response_tokens = 1000

        self.request_tokens = self.max_tokens - self.response_tokens - 100

    def string(self) -> str:
        return f"max_tokens={self.max_tokens}, request_tokens={self.request_tokens}, response_tokens={self.response_tokens}"
