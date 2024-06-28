import re
from enum import Enum
from collections import deque
from stream_bench.agents.base import Agent

class Method(Enum):
    GROW_PROMPT = "grow_prompt"

class ScratchPadAgent(Agent):
    METHODS = {member.value for member in Method}
    CHUNK_DELIMITER = "\n\n\n"

    def __init__(self, config: dict) -> None:
        assert config["agent_name"] in self.METHODS
        assert config["mode"] in {"only_correct", "only_incorrect", "normal"}
        self.mode = config["mode"]
        super().__init__(config)
        self.method = config["agent_name"]
        self.top_k = int(config["top_k"])  # Preserve information about the most recent k instances on the scratchpad (suitable for GrowPrompt, ...)
        self.dq = deque()  # Deque for implementing sliding window (constant time operations)

    def __call__(
        self,
        question: str,
        prompt_zeroshot: str,
        fewshot_template: str,
        **kwargs
    ):
        error_msg = ""
        # Determine the contents
        chunks = list()
        y_chunks = list()
        n_chunks = list()
        not_corr_verb = "not correct"
        
        for chunk in self.dq:
            if chunk.strip().endswith(not_corr_verb):
                n_chunks.append(chunk)
            else:
                y_chunks.append(chunk)
        
        if self.mode == "normal":
            chunks = self.dq
        elif self.mode == "only_correct":
            chunks = y_chunks
        elif self.mode == "only_incorrect":
            chunks = n_chunks
        
        contents = ""
        if len(chunks) > 0:
            contents = self.CHUNK_DELIMITER.join(chunks).replace("\\", "\\\\")  # make it a raw string
            try:
                prompt = re.sub(pattern=r"\{fewshot_text\}", repl=contents, string=fewshot_template)
            except Exception as e:
                error_msg = f"Error ```{e}``` caused by these shots. Logged to jsonl."
                print(error_msg)
                prompt = prompt_zeroshot                
        else:
            prompt = prompt_zeroshot
        # Inference
        pred_text, pred_info = self.llm(prompt=prompt, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
        # logging
        self.update_log_info(log_data={
            "num_chunks": str(len(chunks)),
            "num_correct_chunks": str(len(y_chunks)),
            "num_incorrect_chunks": str(len(n_chunks)),
            "chunks": contents,
            "input_pred": prompt,
            "output_pred": pred_text,
            "logprobs_pred": pred_info["logprobs"],
            "num_inference_call": 1,
            "num_success_call": 1 if (pred_text[:5] != "error") else 0,
            "num_input_tokens": pred_info["num_input_tokens"],
            "num_output_tokens": pred_info["num_output_tokens"],
            "error_msg": error_msg
        })
        return pred_text

    def update(self, has_feedback: bool, **feedbacks) -> bool:
        question = feedbacks["question"]
        if self.method == Method.GROW_PROMPT.value:
            assert ("self_output" in feedbacks) and ("is_correct" in feedbacks)
            answer = feedbacks["self_output"]
            if feedbacks["is_correct"]:
                corr_verb = "correct"
            else:
                corr_verb = "not correct"
            correctness_text = f"Your answer is {corr_verb}"
        else:
            raise NotImplementedError

        if self.method == Method.GROW_PROMPT.value:
            chunk = feedbacks["memprompt_template"].format(
                        question=question,
                        answer=answer,
                        correctness=correctness_text
                    )
            self.dq.append(chunk)
            if len(self.dq) > self.top_k:
                self.dq.popleft()
        else:
            raise NotImplementedError
        return True

    def get_name(self) -> str:
        return "__".join([
            f'{self.config["agent_name"]}-{self.config["mode"]}',
            self.llm_config["series"],
            self.llm_config["model_name"],
            str(self.config["top_k"]) + "-chunks",
            f"seed-{self.config['seed']}"
        ])
