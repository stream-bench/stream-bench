import re
import json
import random
import numpy as np
from enum import Enum
from colorama import Fore, Style

from stream_bench.agents.base import Agent
from stream_bench.agents.utils import RAG, get_llm, setup_logger
from stream_bench.benchmarks.utils import extract_json_string

class Method(Enum):
    RR = "ma_rr"  # multi-agent round-robin; NOTE: the round-robin MAM-StreamICL method in our StreamBench paper
    TS = "ma_ts"  # multi-agent Thompson sampling
    DTS = "ma_dts"  # multi-agent dynamic Thompson sampling
    RR_COT = "ma_rr_cot"  # multi-agent round-robin with CoT

class MultiAgent(Agent):
    METHODS = {member.value for member in Method}
    C = 100  # a predefined hyperparameter for Dynamic Thompson Sampling

    def __init__(self, config: dict) -> None:
        assert config["agent_name"] in self.METHODS
        self.seed = config["seed"]
        random.seed(self.seed)
        np.random.seed(self.seed)
        self.method = config["agent_name"]
        self.warmup_steps = config["warmup_steps"]  # Use round-robin for the first warmup_steps
        # Originally in super().__init__()
        self.config = config
        self.llms = [get_llm(llm["series"], llm["model_name"]) for llm in config["llms"]]
        self.exp_name = config["exp_name"] if "exp_name" in config else self.get_name()
        self.log_path = f'log/{config["bench_name"]}/{config["split"]}/{self.exp_name}'
        self.logger = setup_logger(name="jsonlines_logger", log_file=f'{self.log_path}.jsonl')
        self.llm_names = [llm["model_name"] for llm in config["llms"]]
        self.LOG_KEYS += [llm["model_name"] for llm in config["llms"]]
        self.log_info = {KEY: 0 for KEY in self.LOG_KEYS}  # log information of the current data point
        self.accum_log_info = {KEY: 0 for KEY in self.LOG_KEYS}  # accum_log_info: accumulation of self.log_info through time steps
        # Initialize information for each agent arm
        self.K = len(self.llms)  # number of agents
        self.S = np.zeros(self.K)  # sum of rewards for each arm
        self.F = np.zeros(self.K)  # sum of (1 - reward)s for each arm
        self.cur_arm = 0
        self.algo_name = self.method.split("_")[1]
        self.total_steps = 0
        # RAG
        if config["rag"]["rag_filename"] is None:
            config["rag"]["rag_filename"] = self.log_path + ".db"
        self.rag = RAG(config["rag"])
        self.cur_rationale = None  # for the case of Method.RR_COT

    def __call__(
        self,
        question: str,
        prompt_zeroshot: str,
        fewshot_template: str,
        prompt_cot: str,
        fewshotcot_template: str,
        **kwargs
    ) -> str:
        shots = self.rag.retrieve(query=question, top_k=self.rag.top_k) if (self.rag.insert_acc > 0) else []
        # Determine prompt
        if self.method == Method.RR_COT.value:
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
                shots.append(error_msg)
                prompt = template_wo_rag
        else:
            prompt = template_wo_rag
        # Inference
        if self.total_steps < self.warmup_steps:
            arm = self.pull_rr()
        else:
            arm = getattr(self, f"pull_{self.algo_name}")()
        llm = self.llms[arm]
        pred_text, pred_info = llm(
            prompt=prompt,
            max_tokens=self.config["llms"][arm]["max_tokens"],
            temperature=self.config["llms"][arm]["temperature"]
        )
        # Logging
        self.update_log_info(log_data={
            self.llm_names[arm]: 1,
            "num_shots": str(len(shots)),
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
        if self.method == Method.RR_COT.value:
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
        assert ("self_output" in feedbacks) and ("is_correct" in feedbacks) and ("question" in feedbacks)
        self.update_cur_arm(is_correct=feedbacks["is_correct"])
        if not feedbacks["is_correct"]:
            return False
        question = feedbacks["question"]
        answer = feedbacks["self_output"]
        if self.method == Method.RR_COT.value:
            chunk = feedbacks["shot_template"].format(question=question + f"\nRationale: {self.cur_rationale}", answer=answer)
        else:
            chunk = feedbacks["shot_template"].format(question=question, answer=answer)
        self.rag.insert(key=question, value=chunk)
        return True

    def update_cur_arm(self, is_correct: bool) -> None:
        self.total_steps += 1
        k = self.cur_arm
        if is_correct:
            if (self.method == Method.DTS.value) and (self.S[self.cur_arm] + self.F[self.cur_arm] >= self.C):
                self.S[k] = (self.S[k] + 1) * self.C / (self.C + 1)
                self.F[k] = (self.F[k] + 0) * self.C / (self.C + 1)
                assert abs(self.S[k] + self.F[k] - self.C) < 1
            else:
                self.S[k] += 1
        else:
            if (self.method == Method.DTS.value) and (self.S[self.cur_arm] + self.F[self.cur_arm] >= self.C):
                self.S[k] = (self.S[k] + 0) * self.C / (self.C + 1)
                self.F[k] = (self.F[k] + 1) * self.C / (self.C + 1)
                assert abs(self.S[k] + self.F[k] - self.C) < 1
            else:
                self.F[k] += 1

    def pull_rr(self) -> int:
        self.cur_arm = (self.cur_arm + 1) % self.K
        return self.cur_arm

    def pull_ts(self) -> int:
        # Thompson sampling
        theta = np.random.beta(self.S + 1, self.F + 1)
        self.cur_arm = np.argmax(theta)
        return self.cur_arm

    def pull_dts(self) -> int:
        # The same as Thompson sampling but with a dynamic C (updated in self.update())
        theta = np.random.beta(self.S + 1, self.F + 1)
        self.cur_arm = np.argmax(theta)
        return self.cur_arm

    def get_name(self) -> str:
        llm_names = [llm["model_name"] for llm in self.config["llms"]]
        return "__".join([
            self.config["agent_name"],
            "_".join(llm_names),
            self.config["rag"]["embedding_model"].split('/')[-1],  # remove '/' to avoid incorrect path
            self.config["rag"]["order"],
            str(self.config["rag"]["top_k"]),
            f"warmup-{self.warmup_steps}",
            f"seed-{self.seed}"
        ])
