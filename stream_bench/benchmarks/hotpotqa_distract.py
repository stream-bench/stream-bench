import re
import json
import string
import random
import textwrap
from datasets import Dataset

from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.utils import strip_all_lines, extract_json_string

def normalize_text(s):
    """Removing articles and punctuation, and standardizing whitespace are all typical text processing steps."""

    def remove_articles(text):
        regex = re.compile(r"\b(a|an|the)\b", re.UNICODE)
        return re.sub(regex, " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))

def compute_exact_match(prediction: str, truth: str) -> int:
    return int(normalize_text(prediction) == normalize_text(truth))

def compute_f1(prediction: str, truth: str) -> float:
    pred_tokens = normalize_text(prediction).split()
    truth_tokens = normalize_text(truth).split()
    
    # if either the prediction or the truth is no-answer then f1 = 1 if they agree, 0 otherwise
    if len(pred_tokens) == 0 or len(truth_tokens) == 0:
        return int(pred_tokens == truth_tokens)
    
    common_tokens = set(pred_tokens) & set(truth_tokens)
    
    # if there are no common tokens then f1 = 0
    if len(common_tokens) == 0:
        return 0
    
    prec = len(common_tokens) / len(pred_tokens)
    rec = len(common_tokens) / len(truth_tokens)
    
    return 2 * (prec * rec) / (prec + rec)

class HotpotQADistract(Bench):
    DATASET_PATH = "appier-ai-research/StreamBench"
    DATASET_NAME = "hotpotqa_distract"
    TEST_SIZE = 1500
    NUM_SHOTS = 4

    def __init__(
        self,
        split: str = "validation",
        seed: int = 0,
        feedback: str = "correctness",
        setting: str = "gold_only",  # gold_only, distractor
        **kwargs
    ) -> None:
        assert setting in {"gold_only", "distractor"}
        self.setting = setting
        super().__init__({})
        self.split = split
        self.seed = seed
        self.feedback = feedback
        self.ems = list()
        self.f1s = list()
        self.fewshot_text = self.get_fewshot_text()

    def get_dataset(self) -> Dataset:
        # select the first TEST_SIZE examples from the dataset
        return self.dataset[self.split].select(range(self.TEST_SIZE)).shuffle(seed=self.seed)

    def get_input(self, row: dict) -> dict:
        # Prepare variables
        question = row["question"].strip()
        context = self.get_context(row)
        # Prepare row_input
        row_input = {key: row[key] for key in ["id", "level"]}
        row_input["question"] = question
        row_input["prompt_zeroshot"] = self.get_zeroshot_prompt(context=context, question=question)
        row_input["prompt_fewshot"] = self.get_fewshot_prompt(context=context, question=question)
        row_input["prompt_cot"] = self.get_cot_prompt(context=context, question=question)
        row_input["fewshot_template"] = self.get_fewshot_template(context=context, question=question)
        return row_input

    def get_output(self, row: dict) -> str:
        return row["answer"].strip()

    def get_context(self, row: dict) -> str:
        """Get the context paragraphs for the given row.
        
        Format:
        Title: <title>
        Paragraph: <paragraph>
        
        Title: <title>
        Paragraph: <paragraph>
        ...
        """
        context = row["context"]
        assert len(context["title"]) == len(context["sentences"])
        if self.setting == "gold_only":
            titles = set(row["supporting_facts"]["title"])
        elif self.setting == "distractor":
            titles = set(context["title"])
        chunks = list()
        for title, sentences in zip(context["title"], context["sentences"]):
            if title in titles:
                title_text = f"Title: {title.strip()}"
                paragraph = f"Paragraph: {''.join(sentences).strip()}"
                chunk = '\n'.join([title_text, paragraph])
                chunks.append(chunk)
        return "\n\n".join(chunks)

    @staticmethod
    def get_zeroshot_prompt(context: str, question: str) -> str:
        """Get the zero-shot prompt for the given context and question"""
        prompt = textwrap.dedent(f"""\
        You are doing a question-answering task. You are given the following context, which might help you answer the question:
        
        Context (enclosed in triple backticks):
        ```
        {context}
        ```
        
        Question: {question}
        
        Note that you only need to answer with a short text span without explanation. Now, provide your answer in the following JSON format:
        {{"answer": "<your answer text span>"}}""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_cot_prompt(context: str, question: str) -> str:
        prompt = textwrap.dedent(f"""\
        You are doing a question-answering task. You are given the following context, which might help you answer the question:
        
        Context (enclosed in triple backticks):
        ```
        {context}
        ```
        
        Question: {question}
        
        Let's take a deep breath and work on this problem step-by-step to derive the answer.
        Now, provide your answer in the following JSON format:
        {{"rationale": "<your rationale>", "answer": "<your answer text span>"}}

        Note that <your answer text span> should only be a short text span without explanation.""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_fewshot_template(context: str, question: str) -> str:
        prompt = textwrap.dedent(f"""\
        You are doing a question-answering task. Here are some example cases:
        
        {{fewshot_text}}
        
        Now you are given the following context, which might help you answer the question:
        
        Context:
        ```
        {context}
        ```
        Question: {question}

        Note that you only need to answer with a short text span without explanation. Now, provide your answer in the following JSON format:
        {{"answer": "<your answer text span>"}}""")
        return strip_all_lines(prompt)

    def get_fewshot_prompt(self, context: str, question: str) -> str:
        fewshot_template = self.get_fewshot_template(context, question)
        return re.sub(r"\{fewshot_text\}", self.fewshot_text, fewshot_template)

    @staticmethod
    def get_question_text(context: str, question: str) -> str:
        prompt = textwrap.dedent(f"""\
        Context:
        ```
        {context}
        ```
        Question: {question}""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_shot_template() -> str:
        prompt = textwrap.dedent(f"""\
        {{question}}
        {{answer}}""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_memprompt_template() -> str:
        prompt = textwrap.dedent(f"""\
        {{question}}
        Your answer: {{answer}}
        User Feedback: {{correctness}}""")
        return strip_all_lines(prompt)

    def get_fewshot_text(self) -> str:
        shot_rows = self.dataset["train"]
        shots = list()
        for i in range(self.NUM_SHOTS):
            row = shot_rows[i]
            shot = self.get_shot_template().format(
                question=self.get_question_text(context=self.get_context(row), question=row["question"].strip()),
                answer=self.get_label_text(row["answer"].strip())
            )
            shots.append(shot)
        print(f"{len(shots)} shots generated.")
        return "\n\n\n".join(shots).replace("\\", "\\\\")

    def get_label_text(self, label: str | dict) -> str:
        if isinstance(label, dict) and "answer" in label:
            return json.dumps(label)
        elif isinstance(label, str):
            return json.dumps({"answer": label})
        raise ValueError(f"Invalid label type: {type(label)}")

    def postprocess_generation(self, res: str, idx: int = -1) -> str:
        # Parse the answer out of Answer: '<answer>'
        json_str = extract_json_string(res)
        try:
            obj = json.loads(json_str)
            if "answer" not in obj:
                print(f"Failed to find 'answer' key in the response: {json_str}")
                answer = json_str
            else:
                answer = obj["answer"]
        except json.JSONDecodeError:
            print(f"Failed to parse answer from the response: {res}")
            answer = res
        return answer

    def process_results(
        self,
        prediction: str,
        label: str,
        return_details: bool = True,
        **kwargs
    ) -> dict | bool:
        em = compute_exact_match(prediction, label)
        f1 = compute_f1(prediction, label)
        self.ems.append(em)
        self.f1s.append(f1)
        if return_details:
            return {
                "correct": em,
                "rolling_em": sum(self.ems) / len(self.ems),
                "rolling_f1": sum(self.f1s) / len(self.f1s),
            }
        return em

    def get_metrics(self) -> dict:
        return {
            "em": sum(self.ems) / len(self.ems),
            "f1": sum(self.f1s) / len(self.f1s),
        }

    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        answer = self.postprocess_generation(model_output)
        has_feedback = True
        feedbacks = {
            "question": self.get_question_text(context=self.get_context(row), question=row["question"].strip()),
            "self_output": self.get_label_text(answer),
            "is_correct": res["correct"],
            "ground_truth": self.get_label_text(row["answer"].strip()),
            "shot_template": self.get_shot_template(),
            "memprompt_template": self.get_memprompt_template()
        }
        return has_feedback, feedbacks
