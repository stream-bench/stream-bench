import os
from groq import Groq

from stream_bench.llms.base import LLM
from stream_bench.llms.utils import retry_with_exponential_backoff

class GroqModel(LLM):

    def __init__(self, model_name: str = "llama3-8b-8192") -> None:
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.model_name = model_name

    @retry_with_exponential_backoff
    def __call__(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs
    ) -> tuple[str, dict]:
        chat_completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        res_text = chat_completion.choices[0].message.content
        res_info = {
            "input": prompt,
            "output": res_text,
            "num_input_tokens": chat_completion.usage.prompt_tokens,
            "num_output_tokens": chat_completion.usage.completion_tokens,
            "logprobs": []  # NOTE: Groq currently does not provide logprobs
        }
        return res_text, res_info

if __name__ == "__main__":
    from pprint import pprint
    llm = GroqModel()
    res_text, res_info = llm(prompt="Say apple!")
    print(res_text)
    print()
    pprint(res_info)
