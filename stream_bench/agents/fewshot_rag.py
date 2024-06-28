import re
from enum import Enum

from stream_bench.agents.base import Agent
from stream_bench.agents.utils import parse_pred_text, text_in_label_set, RAG

class Method(Enum):
    CORRECT_SELF = "self_stream_icl"
    MEM_PROMPT = "mem_prompt"

class FewShotRAGAgent(Agent):
    """Few-shot RAG agent for the following baselines (based on the config):

    1. Save all self-generated outputs (all y_hat)
    2. Make save decision (whether to save) + save self-generated outputs (partial y_hat)
    3. Save ground truth outputs (if provided)
    """
    LOG_KEYS_FOR_PROMPT = [
        "input_pred",
        "output_pred",
        "logprobs_pred",
        "input_parse",
        "output_parse",
        "logprobs_parse",
        "input_savedecision",
        "output_savedecision",
        "logprobs_savedecision"
    ]
    METHODS = {member.value for member in Method}

    def __init__(self, config: dict) -> None:
        assert config["agent_name"] in self.METHODS
        if ("mode" in config) and (config["agent_name"] == Method.MEM_PROMPT.value):
            assert config["mode"] in {"only_correct", "only_incorrect", "normal"}
            self.mode = config["mode"]
        else:
            self.mode = "normal"
        super().__init__(config)
        self.method = config["agent_name"]
        if config["rag"]["rag_filename"] is None:
            config["rag"]["rag_filename"] = self.log_path + ".db"
        self.rag = RAG(config["rag"])
        self.update_cnt = 0

    def __call__(
        self,
        question: str,
        prompt_zeroshot: str,
        fewshot_template: str,
        parse_template: str = None,
        label_set: set[str] = None,
        **kwargs
    ) -> str:
        if label_set is not None:
            assert parse_template is not None
        # Retrieve few-shot examples
        shots = self.rag.retrieve(query=question, top_k=self.rag.top_k) if (self.rag.insert_acc > 0) else []  # seems redundant but to ensure flexibility of .retrieve()
        y_shots = list()
        n_shots = list()
        not_corr_verb = "not correct"
        
        for shot in shots:
            if shot.strip().endswith(not_corr_verb):
                n_shots.append(shot)
            else:
                y_shots.append(shot)
        
        if self.mode == "only_correct":
            shots = y_shots
        elif self.mode == "only_incorrect":
            shots = n_shots
        
        if len(shots):
            fewshot_text = "\n\n\n".join(shots).replace("\\", "\\\\")
            try:
                prompt = re.sub(pattern=r"\{fewshot_text\}", repl=fewshot_text, string=fewshot_template)
            except Exception as e:
                error_msg = f"Error ```{e}``` caused by these shots. Logged to jsonl."
                print(error_msg)
                shots.append(error_msg)  # For analyzing errors afterwards
                prompt = prompt_zeroshot
        else:
            prompt = prompt_zeroshot
        # Inference
        pred_text, pred_info = self.llm(prompt=prompt, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
        # logging
        self.update_log_info(log_data={
            "num_shots": str(len(shots)),
            "num_correct_shots": str(len(y_shots)),
            "num_incorrect_shots": str(len(n_shots)),
            "retrieved_shots": shots,
            "input_pred": prompt,
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
        question = feedbacks["question"]
        if self.method == Method.CORRECT_SELF.value:
            assert ("self_output" in feedbacks) and ("is_correct" in feedbacks)
            if not feedbacks["is_correct"]:
                return False  # If not correct -> Do not update RAG
            answer = feedbacks["self_output"]
        elif self.method == Method.MEM_PROMPT.value:
            assert ("self_output" in feedbacks) and ("is_correct" in feedbacks)
            answer = feedbacks["self_output"]
            # Determine the verbalized form of correctness (corr_verb)
            if feedbacks["is_correct"]:
                corr_verb = "correct"
            else:
                corr_verb = "not correct"
            correctness_text = f"Your answer is {corr_verb}"
        else:
            raise NotImplementedError

        if self.method == Method.MEM_PROMPT.value:
            chunk = feedbacks["memprompt_template"].format(question=question, answer=answer, correctness=correctness_text)
        else:
            chunk = feedbacks["shot_template"].format(question=question, answer=answer)
        if (self.bench.DATASET_PATH == "hotpot_qa") and (self.bench.DATASET_NAME == "distractor"):
            index = question.index("Question:")
            question = question[index:].strip()
            if self.update_cnt == 0:
                print("Embed question using only the question itself.")
        self.rag.insert(key=question, value=chunk)
        self.update_cnt += 1
        return True

    def get_name(self) -> str:
        return "__".join([
            f'{self.config["agent_name"]}-{self.config["mode"]}',
            self.llm_config["series"],
            self.llm_config["model_name"],
            self.config["rag"]["embedding_model"].split('/')[-1],  # remove '/' to avoid incorrect path
            self.config["rag"]["order"],
            str(self.config["rag"]["top_k"]),
            f"seed-{self.config['seed']}"
        ])
