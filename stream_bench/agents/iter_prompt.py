import re
from enum import Enum

from stream_bench.agents.base import Agent
from stream_bench.benchmarks.base import Bench

class Method(Enum):
    REACT = "react"
    SELF_REFINE = "self_refine"
    REACT_STREAM_ICL = "react_stream_icl"
    SELF_REFINE_STREAM_ICL = "self_refine_stream_icl"

class IterPromptAgent(Agent):
    METHODS = {member.value for member in Method}
    NUM_ITER = 4

    def __init__(self, config: dict) -> None:
        assert config["agent_name"] in self.METHODS
        self.method = config["agent_name"]
        super().__init__(config)
        self.bench: Bench = None
        self.refine_trajectory = None
        self.react_trajectory = None
        # RAG configs
        if self.method in {Method.REACT_STREAM_ICL.value, Method.SELF_REFINE_STREAM_ICL.value}:
            raise NotImplementedError

    def __call__(
        self,
        **kwargs
    ) -> str:
        return getattr(self, self.method)(**kwargs)

    def update(self, has_feedback: bool, **feedbacks) -> bool:
        return False

    def self_refine(
        self,
        prompt_zeroshot: str,  # initial generation (i.e., p_gen in the Self-Refine paper)
        feedback_template: str,
        refine_template: str,
        **kwargs
    ) -> str:
        self.init_refine_trajectory()
        self.reset_log_info()
        # Self-Refine algorithm
        yt, yt_info = self.llm(prompt=prompt_zeroshot, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
        self.update_log_info(log_data={
            "input_gen": prompt_zeroshot,
            "output_gen": yt,
            "logprobs_gen": yt_info["logprobs"],
            "num_inference_call": 1,
            "num_input_tokens": yt_info["num_input_tokens"],
            "num_output_tokens": yt_info["num_output_tokens"]
        })
        for t in range(self.NUM_ITER):
            prompt_fb = self.get_feedback_prompt(feedback_template, y_hat=yt)
            fbt, fbt_info = self.llm(prompt=prompt_fb, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
            self.update_log_info(log_data={
                f"input_fb_{t}": prompt_fb,
                f"output_fb_{t}": fbt,
                f"logprobs_fb_{t}": fbt_info["logprobs"],
                "num_inference_call": 1,
                "num_input_tokens": fbt_info["num_input_tokens"],
                "num_output_tokens": fbt_info["num_output_tokens"]
            })
            if self.meet_stop_condition(fb=fbt):
                break
            self.update_refine_trajectory(yt, fbt)
            prompt_refine = self.get_refine_prompt(refine_template, trajectory=self.get_refine_trajectory())
            yt, yt_info = self.llm(prompt=prompt_refine, max_tokens=self.llm_config["max_tokens"], temperature=self.llm_config["temperature"])
            self.update_log_info(log_data={
                f"input_refine_{t}": prompt_refine,
                f"output_refine_{t}": yt,
                f"logprobs_refine_{t}": yt_info["logprobs"],
                "num_inference_call": 1,
                "num_input_tokens": yt_info["num_input_tokens"],
                "num_output_tokens": yt_info["num_output_tokens"]
            })
        return yt

    def meet_stop_condition(
        self,
        fb: str
    ) -> bool:
        """The extracted JSON string should at least has the key "need_refinement"."""
        if "NO NEED TO REFINE" in fb:
            return True
        return False

    def init_refine_trajectory(self) -> None:
        self.refine_trajectory = list()

    def update_refine_trajectory(self, yt: str, fbt: str) -> None:
        """Trajectory format:
        
        [
            {"answer": <yt>, "feedback": <suggestion_in_fbt>},
            {"answer": <yt>, "feedback": <suggestion_in_fbt>},
            ...   
        ]
        """
        self.refine_trajectory.append({"answer": yt, "feedback": fbt})

    def get_refine_trajectory(self) -> str:
        """Note: The format of answer-feedback trajectory should be as follows
        
        Answer 0: <SQL_code_0>
        Feedback 0: <feedback_0>
        Answer 1: <SQL_code_1>
        Feedback 1: <feedback_1>
        ...
        Answer k: <SQL_code_n>
        Feedback k: <feedback_n>
        """
        trajectory = list()
        for t in range(len(self.refine_trajectory)):
            answer = self.refine_trajectory[t]["answer"].strip()
            feedback = self.refine_trajectory[t]["feedback"].strip()
            trajectory.append(f"Answer {t}: {answer}")
            trajectory.append(f"Feedback {t}: {feedback}")
        return '\n'.join(trajectory)

    @staticmethod
    def get_feedback_prompt(
        template: str,
        y_hat: str
    ) -> str:
        y_hat = y_hat.replace("\\", "\\\\")
        return re.sub(pattern=r"\{y_hat\}", repl=y_hat, string=template)

    @staticmethod
    def get_refine_prompt(
        template: str,
        trajectory: str
    ) -> str:
        trajectory = trajectory.replace("\\", "\\\\")
        prompt = re.sub(pattern=r"\{trajectory\}", repl=trajectory, string=template)
        return prompt

    def get_name(self) -> str:
        name = "__".join([
            self.config["agent_name"],
            self.llm_config["series"],
            self.llm_config["model_name"],
        ])
        if self.method in {Method.REACT_STREAM_ICL.value, Method.SELF_REFINE_STREAM_ICL.value}:
            stream_suffix = "__".join([
                self.config["rag"]["embedding_model"].split('/')[-1],
                self.config["rag"]["order"],
                str(self.config["rag"]["top_k"])
            ])
            name += f"__{stream_suffix}"
        return name
