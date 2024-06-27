import os
import logging
import vertexai
import vertexai.preview.generative_models as generative_models
from time import sleep
from vertexai.preview.generative_models import GenerativeModel
from stream_bench.llms.utils import retry_with_exponential_backoff
vertexai.init(project=os.environ['GCP_PROJECT_NAME'], location="us-central1")

class Gemini():
    SAFETY_SETTINGS={
            generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_NONE,
            generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_NONE,
            generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_NONE,
            generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_NONE,
        }


    def __init__(self, model_name='gemini-1.0-pro-vision-001') -> None:
        self.model = GenerativeModel(model_name)

    @retry_with_exponential_backoff
    def __call__(self, prompt, max_tokens=1024, temperature=0.0, top_p=1, top_k=1) -> str:
        result = self.model.generate_content(
                prompt,
                generation_config={
                    "max_output_tokens": int(max_tokens),
                    "temperature": float(temperature),
                    "top_p": float(top_p),
                    "top_k": int(top_k)
                },
                safety_settings=self.SAFETY_SETTINGS,
                stream=False
        ).candidates[0].content.parts[0].text
        res_info = {
            "input": prompt,
            "output": result,
            "num_input_tokens": self.model.count_tokens(prompt).total_tokens,
            "num_output_tokens": self.model.count_tokens(result).total_tokens,
            "logprobs": []  # NOTE: currently the Gemini API does not provide logprobs
        }
        return result, res_info
