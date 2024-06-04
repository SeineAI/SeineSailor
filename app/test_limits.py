import pytest
from app.limits import TokenLimits

@pytest.mark.parametrize("model, max_token, response_token",[
    ("gpt-4-32k",32600,4000), 
    ("gpt-3.5-turbo-16k",16300,3000), 
    ("mixtral",8000,2000), 
    ("llama-3",8000,2000), 
    ("gpt-4",8000,2000), 
    ("mistral-tiny",32000,4000), 
    ("mistral-small",32000,4000), 
    ("mistral-medium",32000,4000), 
    ("instructlab",4000,1000),
    ("gpt-3.5-turbo",4000,1000)
])
def test_with_model(model,max_token,response_token):
    instance = TokenLimits(model)
    assert instance.max_tokens == max_token
    assert instance.response_tokens == response_token
