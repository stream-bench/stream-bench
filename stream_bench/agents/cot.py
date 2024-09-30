import json
from colorama import Fore, Style

from stream_bench.agents.base import Agent
from stream_bench.benchmarks.utils import extract_json_string

class CoTAgent(Agent):
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

    def __call__(self, prompt_cot: str, **kwargs) -> str:
        # Initialize variable for tracking
        self.reset_log_info()
        # Inference
        if self.config.get("mode", None) == "json":
            prompt_cot = kwargs["prompt_cot_json"]
        pred_text, pred_info = self.llm(prompt=prompt_cot, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
        # logging
        self.update_log_info(log_data={
            "input_pred": prompt_cot,
            "output_pred": pred_text,
            "logprobs_pred": pred_info["logprobs"],
            "num_inference_call": 1,
            "num_success_call": 1 if (pred_text[:5] != "error") else 0,
            "num_input_tokens": pred_info["num_input_tokens"],
            "num_output_tokens": pred_info["num_output_tokens"]
        })
        json_text = extract_json_string(pred_text)
        parse_text = pred_text
        if json_text and (self.config["bench_name"] == "ddxplus"):
            try:
                obj = json.loads(json_text)
                if "rationale" not in obj:
                    parse_text += "\nWarning: rationale not found in the output."
                    print(Fore.YELLOW + "Lack rationale" + Style.RESET_ALL)
                if "answer" not in obj:
                    parse_text += "\nWarning: answer not found in the output"
                    print(Fore.RED + "Lack answer" + Style.RESET_ALL)
                else:
                    parse_text = obj["answer"]
            except json.JSONDecodeError:
                parse_text += "\nError: JSONDecodeError"
                print(Fore.RED + "JSONDecodeError" + Style.RESET_ALL)
        self.update_log_info(log_data={
            "output_json": json_text,
            "output_parse": parse_text
        })
        return parse_text

    def update(self, has_feedback: bool, **feedbacks) -> bool:
        return False
