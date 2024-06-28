from stream_bench.agents.base import Agent

class FewShotAgent(Agent):
    LOG_KEYS_FOR_PROMPT = [
        "input_pred",
        "output_pred",
        "logprobs_pred",
        "input_parse",
        "output_parse",
        "logprobs_parse"
    ]

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def __call__(self, prompt_fewshot: str, **kwargs) -> str:
        # Initialize variable for tracking
        self.reset_log_info()
        # Inference
        pred_text, pred_info = self.llm(prompt=prompt_fewshot, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
        # logging
        self.update_log_info(log_data={
            "input_pred": prompt_fewshot,
            "output_pred": pred_text,
            "logprobs_pred": pred_info["logprobs"],
            "num_inference_call": 1,
            "num_success_call": 1 if (pred_text[:5] != "error") else 0,
            "num_input_tokens": pred_info["num_input_tokens"],
            "num_output_tokens": pred_info["num_output_tokens"]
        })
        return pred_text

    def update(self, has_feedback: bool, **feedbacks) -> bool:
        return False
