from abc import ABC, abstractmethod

class LLM(ABC):
    @abstractmethod
    def __init__(self) -> None:
        """Setup LLM configs here"""
        raise NotImplementedError

    @abstractmethod
    def __call__(self, prompt: str, max_tokens: int = 1024, temperature=0.0, **kwargs) -> tuple[str, dict]:
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
        raise NotImplementedError
