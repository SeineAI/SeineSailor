import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")


def encode(input_text: str) -> list:
    return tokenizer.encode(input_text)


def get_token_count(input_text: str) -> int:
    input_text = input_text.replace("<|endoftext|>", "")
    return len(encode(input_text))
