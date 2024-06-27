from .base import Agent
from .utils import text_in_label_set, parse_pred_text

class ZeroShotAgent(Agent):
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

    def __call__(self, prompt_zeroshot: str, parse_template: str = None, label_set: set[str] = None, **kwargs) -> str:
        if label_set is not None:
            assert parse_template is not None
        # Initialize variable for tracking
        self.reset_log_info()
        # Inference
        pred_text, pred_info = self.llm(prompt=prompt_zeroshot, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
        # logging
        self.update_log_info(log_data={
            "input_pred": prompt_zeroshot,
            "output_pred": pred_text,
            "logprobs_pred": pred_info["logprobs"],
            "num_inference_call": 1,
            "num_success_call": 1 if (pred_text[:5] != "error") else 0,
            "num_input_tokens": pred_info["num_input_tokens"],
            "num_output_tokens": pred_info["num_output_tokens"]
        })
        if label_set is not None:
            # (Optional) Parse pred_text into one of the labels in label_set
            pred_text = parse_pred_text(pred_text, label_set)  # simple heuristics for removing leading and trailing characters
            if not text_in_label_set(text=pred_text, label_set=label_set):
                prompt_parse = parse_template.format(model_output=pred_text)
                parse_text, parse_info = self.llm(prompt=prompt_parse, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
                self.update_log_info(log_data={
                    "input_parse": prompt_parse,
                    "output_parse": parse_text,
                    "logprobs_parse": parse_info["logprobs"],
                    "num_inference_call": 1,
                    "num_success_call": 1 if (parse_text[:5] != "error") else 0,
                    "num_input_tokens": parse_info["num_input_tokens"],
                    "num_output_tokens": parse_info["num_output_tokens"]
                })
                return parse_text
        return pred_text

    def update(self, has_feedback: bool, **feedbacks) -> bool:
        return False
