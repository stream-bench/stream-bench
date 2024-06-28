import os
import google.generativeai as genai

from stream_bench.llms.utils import retry_with_exponential_backoff

class GeminiDev:
    SAFETY_SETTINGS=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    def __init__(self, model_name: str = "gemini-1.0-pro") -> None:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel(model_name)

    @retry_with_exponential_backoff
    def __call__(self, prompt: str, max_tokens=512, temperature=0.0, top_p=1, top_k=1) -> tuple[str, dict]:
        """Returns the tuple of the response text as well as other detailed info."""
        res = self.model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": int(max_tokens),
                "temperature": float(temperature),
                "top_p": float(top_p),
                "top_k": int(top_k)
            },
            safety_settings=self.SAFETY_SETTINGS,
            stream=False
        )
        res_info = {
            "input": prompt,
            "output": res.text,
            "num_input_tokens": self.model.count_tokens(prompt).total_tokens,
            "num_output_tokens": self.model.count_tokens(res.text).total_tokens,
            "logprobs": []  # NOTE: currently the Gemini API does not provide logprobs
        }
        return res.text, res_info
