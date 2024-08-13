import re
import json
from enum import Enum
from colorama import Fore, Style

from stream_bench.agents.base import Agent
from stream_bench.agents.utils import RAG
from stream_bench.benchmarks.utils import extract_json_string

class Method(Enum):
    CORRECT_SELF_COT = "self_stream_icl_cot"
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
        self.cur_rationale = None  # for the case of "self_stream_icl_cot"

    def __call__(
        self,
        question: str,
        prompt_zeroshot: str,
        fewshot_template: str,
        prompt_cot: str,
        fewshotcot_template: str = None,
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
        
        if self.method == Method.CORRECT_SELF_COT.value:
            template_w_rag = fewshotcot_template
            template_wo_rag = prompt_cot
        else:
            template_w_rag = fewshot_template
            template_wo_rag = prompt_zeroshot
        if len(shots):
            fewshot_text = "\n\n\n".join(shots).replace("\\", "\\\\")
            try:
                prompt = re.sub(pattern=r"\{fewshot_text\}", repl=fewshot_text, string=template_w_rag)
            except Exception as e:
                error_msg = f"Error ```{e}``` caused by these shots. Logged to jsonl."
                print(error_msg)
                shots.append(error_msg)  # For analyzing errors afterwards
                prompt = template_wo_rag
        else:
            prompt = template_wo_rag
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
        # Extract rationale if CoT is used
        if self.method == Method.CORRECT_SELF_COT.value:
            json_text = extract_json_string(pred_text)
            parse_text = pred_text
            if json_text and (self.config["bench_name"] == "ddxplus"):
                try:
                    obj = json.loads(json_text)
                    if "rationale" not in obj:
                        parse_text += "\nWarning: rationale not found in the output."
                        print(Fore.YELLOW + "Lack rationale" + Style.RESET_ALL)
                    else:
                        self.cur_rationale = obj["rationale"]
                    if "answer" not in obj:
                        parse_text += "\nWarning: answer not found in the output"
                        print(Fore.RED + "Lack answer" + Style.RESET_ALL)
                    else:
                        parse_text = obj["answer"]
                except json.JSONDecodeError:
                    parse_text += "\nError: JSONDecodeError"
                    print(Fore.RED + "JSONDecodeError" + Style.RESET_ALL)
            return parse_text
        return pred_text

    def update(self, has_feedback: bool, **feedbacks) -> bool:
        question = feedbacks["question"]
        if self.method in {Method.CORRECT_SELF.value, Method.CORRECT_SELF_COT.value}:
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
        elif self.method == Method.CORRECT_SELF.value:
            chunk = feedbacks["shot_template"].format(question=question, answer=answer)
        elif self.method == Method.CORRECT_SELF_COT.value:
            chunk = feedbacks["shot_template"].format(question=question + f"\nRationale: {self.cur_rationale}", answer=answer)
        else:
            raise NotImplementedError

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
