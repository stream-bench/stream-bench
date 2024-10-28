import re
import random
import evaluate
from datasets import Dataset
from colorama import Fore, Style

from stream_bench.llms.oai_chat import OpenAIChat
from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.utils import strip_all_lines

class GPQABench(Bench):
    """Reference: https://huggingface.co/datasets/Idavidrein/gpqa"""
    DATASET_PATH = "Idavidrein/gpqa"
    NUM_CHOICES = 4
    CHOICES_ALPHABETS = "ABCD"
    TEXT2LABEL = {c: i for i, c in enumerate(CHOICES_ALPHABETS)}
    LABEL2TEXT = {i: c for i, c in enumerate(CHOICES_ALPHABETS)}

    def __init__(
        self,
        split: str = "train",
        seed: int = 42,
        **kwargs
    ) -> None:
        super().__init__({})
        self.split = split
        self.seed = seed
        self.gt = None
        self.llm = OpenAIChat(model_name="gpt-4o-mini-2024-07-18")
        random.seed(seed)

    def get_dataset(self) -> Dataset:
        return self.dataset[self.split].shuffle(seed=self.seed)

    @staticmethod
    def get_choices_sequence(num_choices: int) -> list[int]:
        indices = list(range(num_choices))
        random.shuffle(indices)
        return indices  # The indices are of [<Correct>, <Incorrect 1>, <Incorrect 2>, <Incorrect 3>]

    @staticmethod
    def get_choices(row: dict) -> list[str]:
        return [
            row["Correct Answer"],
            row["Incorrect Answer 1"],
            row["Incorrect Answer 2"],
            row["Incorrect Answer 3"]
        ]

    def get_choices_text_and_ground_truth(self, row: dict) -> tuple[str, int]:
        choices = self.get_choices(row)
        indices = self.get_choices_sequence(self.NUM_CHOICES)
        chunks = [None] * self.NUM_CHOICES
        for i, index in enumerate(indices):
            chunks[index] = f"{self.CHOICES_ALPHABETS[index]}. {choices[i]}".strip()
        return "\n".join(chunks), indices[0]

    def get_zeroshot_prompt(
        self,
        question: str,
        choices_text: str
    ) -> str:
        prompt = f"""\
        Answer the following question based on the provided choices:

        Question: {question}
        
        Choices:
        {choices_text}

        Provide your reasoning process first, then provide your final answer in the following format:
        ANSWER: <letter>"""
        return strip_all_lines(prompt)

    def get_cot_prompt(
        self,
        question: str,
        choices_text: str
    ) -> str:
        prompt = f"""\
        Answer the following question based on the provided choices:

        Question: {question}
        
        Choices:
        {choices_text}

        Now, take a deep breath and work on this problem step-by-step to derive the most likely answer.
        First provide your reasoning, then provide your answer in the following format: {{"answer": "<letter>. <answer>"}}"""
        return strip_all_lines(prompt)

    def get_input(self, row: dict) -> dict:
        question = row["Question"]
        choices_text, gt = self.get_choices_text_and_ground_truth(row)
        self.gt = gt
        return {
            "question": question,
            "choices": self.get_choices(row),
            "prompt_zeroshot": self.get_zeroshot_prompt(question, choices_text),
            "prompt_cot": self.get_cot_prompt(question, choices_text)
        }

    def get_output(self, row: dict) -> str:
        return self.gt

    def get_metrics(self) -> dict:
        accuracy = evaluate.load("accuracy")
        metrics = accuracy.compute(predictions=self.predictions, references=self.references)
        return metrics

    def postprocess_generation(self, res: str, idx: int) -> int:
        if len(res) != 1:
            res = self.parse_answer(res)
            if res not in self.CHOICES_ALPHABETS:
                print(Fore.YELLOW + f"Prediction {res} is not a single letter in {self.CHOICES_ALPHABETS}. Randomly select one." + Style.RESET_ALL)
                res = random.choice(self.CHOICES_ALPHABETS)
        return self.TEXT2LABEL[res]

    def parse_answer(self, res: str) -> str:
        if res[0] in self.CHOICES_ALPHABETS:
            return res[0]
        else:  # search for the <letter> in ANSWER: <letter>
            match = re.search(r"ANSWER: (\w)", res)
            if match:
                return match.group(1)
            else:
                print(Fore.YELLOW + "No ANSWER: <letter> found. Extracting by another LLM inference." + Style.RESET_ALL)
                prompt = f"Extract the final answer from the following LLM-generated text: {res}\nProvide the final answer with a single letter in A, B, C, or D."
                res, _ = self.llm(prompt, max_tokens=1, temperature=0)
                if res in self.CHOICES_ALPHABETS:
                    return res
                else:
                    print(Fore.RED + "Fail to extract by another LLM inference. Returning empty string." + Style.RESET_ALL)
        return ""

    def process_results(
        self,
        prediction: str,
        label: str,
        return_details: bool = True,
        **kwargs
    ) -> bool | dict:
        correctness = prediction == label
        self.n_correct += correctness
        self.predictions.append(prediction)
        self.references.append(label)
        rolling_acc = self.get_metrics()["accuracy"]
        if return_details:
            return {
                "correct": correctness,
                "n_correct": self.n_correct,
                "rolling_acc": rolling_acc
            }
        return correctness

    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        has_feedback = True
        feedbacks = {
            "question": row["Question"],
            "self_output": model_output,
            "is_correct": res["correct"],
            "ground_truth": self.gt,
        }
        return has_feedback, feedbacks

def create_gpqa_diamond():
    class GPQADiamondBench(GPQABench):
        DATASET_NAME = "gpqa_diamond"
    return GPQADiamondBench

def create_gpqa_main():
    class GPQAMainBench(GPQABench):
        DATASET_NAME = "gpqa_main"
    return GPQAMainBench

def create_gpqa_extended():
    class GPQAExtendedBench(GPQABench):
        DATASET_NAME = "gpqa_extended"
    return GPQAExtendedBench
