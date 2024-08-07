import json
import textwrap
import evaluate
from datasets import Dataset
from colorama import Fore, Style

from stream_bench.llms.oai_chat import OpenAIChat
from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.utils import strip_all_lines, extract_json_string

class GSM8KBench(Bench):
    """Benchmark for the GSM8K dataset."""
    DATASET_PATH = "appier-ai-research/robust-finetuning"
    DATASET_NAME = "gsm8k"
    EVAL_LLM = "gpt-4o-mini-2024-07-18"  # for extracting the answer from LLMs' raw output

    def __init__(
        self,
        split: str = "test",
        seed: int = 42,
        feedback: str = "correctness",
        **kwargs
    ) -> None:
        super().__init__({})
        self.split = split
        self.seed = seed
        self.feedback = feedback
        self.eval_func = evaluate.load("exact_match")
        self.llm = OpenAIChat(model_name=self.EVAL_LLM)

    def get_dataset(self) -> Dataset:
        return self.dataset[self.split].shuffle(seed=self.seed)

    @staticmethod
    def get_zeroshot_prompt(question: str) -> str:
        return question

    def get_input(self, row: dict) -> dict:
        row_input = dict()
        row_input["question"] = row["question"]
        row_input["prompt_zeroshot"] = self.get_zeroshot_prompt(row["question"])
        return row_input

    def get_output(self, row: dict) -> dict:
        rna = row["answer"].split("####")
        rationale = rna[0].strip()
        answer = rna[1].strip()
        if ',' in answer:
            answer = ''.join(answer.split(','))
        return {"rationale": rationale, "answer": answer}

    def get_metrics(self) -> dict:
        metrics = self.eval_func.compute(
            predictions=self.predictions,
            references=self.references,
            ignore_punctuation=True
        )
        return metrics

    def postprocess_generation(self, res: str, idx: int = -1) -> str:
        # Parse out the answer with a cheap LLM
        prompt_extract = strip_all_lines("""\
        The following text is an LLM's response to a math question:

        Text (enclosed in triple quotes): '''{text}'''

        Extract the answer from the text (only extract the digits, potentially the sign if the number is negative), and provide it in the following JSON format:
        {{"answer": "<digits>"}}""")
        prompt = prompt_extract.format(text=res)
        answer_str, _ = self.llm(prompt)
        answer_json = extract_json_string(answer_str)
        try:
            answer = json.loads(answer_json)["answer"]
        except (json.JSONDecodeError, KeyError) as e:
            print(Fore.RED + str(e) + Style.RESET_ALL)
            answer = res
        return answer

    def process_results(
        self,
        prediction: str,
        label: dict,
        return_details: bool = True,
        **kwargs
    ) -> bool | dict:
        answer = label["answer"]
        correct = self.eval_func.compute(
            predictions=[prediction],
            references=[answer]
        )["exact_match"]
        self.n_correct += correct
        self.predictions.append(prediction)
        self.references.append(answer)
        if return_details:
            return {
                "correct": int(correct),
                "n_correct": self.n_correct,
                "rolling_em": self.get_metrics()["exact_match"]
            }
        return bool(correct)

    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        return True, {}
