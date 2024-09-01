import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from stream_bench.llms.base import LLM

class HFModel(LLM):

    def __init__(self, model_name: str = "google/gemma-2-2b-it") -> None:
        """Setup LLM configs here"""
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="cuda" if torch.cuda.is_available() else "cpu",
            torch_dtype=torch.bfloat16,
        )
        self.model.eval()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def __call__(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs
    ) -> tuple[str, dict]:
        """Prompt the LLM and get a tuple of (response_text, response_info).
        
        The response_info should be in the following format:
        {
            "input": prompt,
            "output": <response_text>,
            "num_input_tokens": <number_of_input_tokens>,
            "num_output_tokens": <number_of_output_tokens>,
            "logprobs": <log_probs_of_each_token_position>  # please refer to oai_chat.py for the schema
        }
        """
        messages = [{"role": "user", "content": prompt}]
        input_tensor = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt")
        outputs = self.model.generate(
            input_tensor.to(self.model.device),
            max_new_tokens=max_tokens,
            temperature=temperature
        )
        result = self.tokenizer.decode(outputs[0][input_tensor.shape[1]:], skip_special_tokens=True)
        info = {
            "input": prompt,
            "output": result,
            "num_input_tokens": input_tensor.shape[1],
            "num_output_tokens": len(self.tokenizer(text=result)["input_ids"]),
            "logprobs": []  # NOTE: not implemented yet
        }
        return result, info
