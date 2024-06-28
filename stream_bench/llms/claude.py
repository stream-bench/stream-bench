import os
from anthropic import Anthropic

from stream_bench.llms.utils import retry_with_exponential_backoff

class ClaudeChat():

    def __init__(self, model_name='claude-3-opus-20240229') -> None:
        self.client = Anthropic(api_key=os.environ['ANTHROPIC_KEY'])
        self.model_name = model_name

    @retry_with_exponential_backoff
    def __call__(self, prompt, max_tokens=512, temperature=0.0, **kwargs) -> str:
        message = self.client.messages.create(
            max_tokens=int(max_tokens),
            temperature=float(temperature),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            model=self.model_name,
        )
        res_text = message.content[0].text
        res_info = {
            "input": prompt,
            "output": res_text,
            "num_input_tokens": message.usage.input_tokens,
            "num_output_tokens": message.usage.output_tokens,
            "logprobs": []  # NOTE: currently the Claude API does not provide logprobs
        }
        return res_text, res_info

if __name__ == "__main__":
    llm = ClaudeChat(model_name="claude-3-haiku-20240307")
    res_text, res_info = llm(prompt="Hello, there!")
    print(res_text)
    print(res_info)
