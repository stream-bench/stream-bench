import os
import re
import textwrap
from tqdm import tqdm
from datasets import Dataset
from colorama import Fore, Style

from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.text2sql_utils.sqlite_interpreter import execute_model
from stream_bench.benchmarks.text2sql_utils.string_formatter import (
    parse_sql, generate_schema_prompt
)
from stream_bench.benchmarks.utils import strip_all_lines


def create_cosql():
    class StreamingCOSQL(GeneralText2SQL):
        DATASET_PATH = 'appier-ai-research/StreamBench'
        DATASET_NAME = 'cosql'
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    return StreamingCOSQL

def create_spider():
    class StreamingSpider(GeneralText2SQL):
        DATASET_PATH = 'appier-ai-research/StreamBench'
        DATASET_NAME = 'spider'
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    return StreamingSpider


def create_bird():
    class StreamingBird(GeneralText2SQL):
        DATASET_PATH = 'appier-ai-research/StreamBench'
        DATASET_NAME = 'bird'
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
    return StreamingBird


class GeneralText2SQL(Bench):
    """A task represents an entire benchmark including its dataset, problems,
    answers, generation settings and evaluation methods.
    """
    NUM_SHOTS = 16

    def __init__(
        self,
        split: str = "test",
        seed: int = 0,
        feedback: str = "correctness",
        knowledge: bool = False,
        db_path: str = None,
        agent = None,
        agent_callback = None,
        distribution_shift = False,
        **kwargs
    ) -> None:
        super().__init__(config={})
        self.split = split
        self.seed = seed
        self.feedback = feedback
        self.db_path = db_path
        self.feedback = feedback
        self.agent_callback = None
        self.knowledge = knowledge
        self.total = 0
        if distribution_shift:  # order the instances by sorting the field "db_id"
            print(Fore.CYAN + "Sorting the instances by 'db_id' for distribution shift evaluation." + Style.RESET_ALL)
            self.eval_set = self.dataset[self.split].sort("db_id")
        else:
            self.eval_set = self.dataset[self.split].shuffle(seed=self.seed)
        self.initialize()

    def get_dataset(self) -> Dataset:
        """Returns dataset for the task or an iterable of any object, that get_prompt can handle"""
        return self.eval_set

    def initialize(self) -> None:
        print("Initializing DB schema prompts...")
        self.db_prompt_schema = dict()
        for row in tqdm(self.eval_set, dynamic_ncols=True):
            if row["db_id"] not in self.db_prompt_schema:
                db_path = os.path.join(self.db_path, row["db_id"], row["db_id"] + ".sqlite")
                schema_prompt = generate_schema_prompt(db_path)
                self.db_prompt_schema[row["db_id"]] = schema_prompt
        print(len(self.db_prompt_schema), 'found!')
        print("Building few-shot examples...")
        self.fewshot_text = self.get_fewshot_text()

    def postprocess_generation(self, generation: str, idx: int = -1) -> str:
        """Defines the postprocessing for a LM generation.
        :param generation: str
            code generation from LM
        :param idx: int
            index of doc in the dataset to which the generation belongs
            (not used for GeneralText2SQL-Task)
        """
        return parse_sql(generation)

    def get_input(self, row: dict) -> dict:
        row_input = dict()
        schema = self.db_prompt_schema[row["db_id"]]
        # if self.agent_callback is not None:
        #     feedback = self.agent_callback(row)
        #     question_prompt = generate_comment_prompt(row['question'],
        #                                 knowledge=feedback
        #                             )
        # else:
        #     question_prompt = generate_comment_prompt(row['question'],
        #                                 knowledge=row['evidence'] if self.knowledge else None
        #                             )
        # outputs['prompt'] = schema_prompt + '\n\n' + question_prompt + cot_wizard() + '\nSELECT '
        row_input["question"] = row["question"]
        row_input["fewshot_template"] = self.get_fewshot_template(schema=schema, question=row["question"])
        row_input["prompt_zeroshot"] = self.get_zeroshot_prompt(schema=schema, question=row["question"])
        row_input["prompt_fewshot"] = self.get_fewshot_prompt(schema=schema, question=row["question"])
        row_input["prompt_cot"] = self.get_cot_prompt(schema=schema, question=row["question"])
        row_input["feedback_template"] = self.get_feedback_template(schema=schema, question=row["question"])
        row_input["refine_template"] = self.get_refine_template(schema=schema, question=row["question"])
        return row_input

    def get_output(self, row: dict):
        return {"SQL": row["SQL"], "db_id": row["db_id"], 'label': row["SQL"]}

    def process_results(self, generations: str, label: dict, return_details: bool = False, **kwargs):
        """Takes the list of LM generations and evaluates them against ground truth references,
        returning the metric for the generations.
        :param generations: list(list(str))
            list of lists containing generations
        :param labels: original labels
            list of str containing refrences
        """
        db_path = os.path.join(self.db_path, label['db_id'], label['db_id'] + '.sqlite')
        correct = execute_model(generations, label['SQL'], db_path)[0]
        self.n_correct += correct
        self.predictions.append(generations)
        self.references.append(label)
        self.total += 1
        rolling_acc = self.n_correct / self.total
        if return_details:
            return {
                "result": 'Answer is Correct' if correct == 1 else 'Answer is NOT Correct',
                "correct": correct,
                "n_correct": self.n_correct,
                "rolling_acc": rolling_acc
            }
        return correct

    def get_metrics(self):
        return {
            "EX": self.n_correct / self.total
        }

    def give_feedback(self, model_output: str, row: dict, res: dict = None) -> tuple[bool, dict]:
        generation = self.postprocess_generation(model_output, -1)
        db_path = os.path.join(self.db_path, row['db_id'], row['db_id']+'.sqlite')
        correct, results = execute_model(generation, row['SQL'], db_path)
        # return (True, {"feedback_msg" : row['evidence'], "answer_correct": correct })
        pred_str = self.postprocess_generation(model_output)
        has_feedback = True
        feedbacks = {
            "question": row["question"],
            "self_output": pred_str,
            "is_correct": correct,
            "ground_truth": row["SQL"],
            "shot_template": self.get_shot_template(),
            "memprompt_template": self.get_memprompt_template()
        }
        return has_feedback, feedbacks

    @staticmethod
    def get_zeroshot_prompt(schema: str, question: str) -> str:
        prompt = textwrap.dedent(f"""\
        {schema}
        
        -- Using valid SQLite, answer the following question for the tables provided above.
        -- Question: {question}
        
        Now, generate the correct SQL code directly (Do NOT generate other text except the SQL code):""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_cot_prompt(schema: str, question: str) -> str:
        prompt = textwrap.dedent(f"""\
        {schema}
        
        -- Using valid SQLite, answer the following question for the tables provided above.
        -- Question: {question}
        
        Now, take a deep breath and work on this problem step-by-step to derive the correct SQL code.
        Provide your output in the following format:
        Rationale: <your_rationale>
        Answer: ```sql\n<your_SQL_code>\n```""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_fewshot_template(schema: str, question: str) -> str:
        prompt = textwrap.dedent(f"""\
        You are performing the text-to-SQL task. Here are some examples:
        
        {{fewshot_text}}
        
        Now it's your turn.
        
        -- SQL schema: {schema}
        -- Using valid SQLite, answer the following question for the SQL schema provided above.
        -- Question: {question}
        
        Now, generate the correct SQL code directly (Do NOT generate other text except the SQL code):""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_feedback_template(schema: str, question: str) -> str:
        prompt = textwrap.dedent(f"""\
        You are performing the text-to-SQL task. Here is the database schema, user's question, and your previously generated SQL code.
        
        -- SQL schema: {schema}
        -- User's question: {question}
        -- Your SQL code: {{y_hat}}
        
        First, determine whether you need to refine your SQL code in terms of its correctness.
        If you consider that your SQL code is correct, output 'NO NEED TO REFINE' in uppercase.
        Otherwise, provide a suggestion to correct the SQL code.""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_refine_template(schema: str, question: str) -> str:
        """Note: The format of answer-feedback trajectory should be as follows
        
        Answer 0: <SQL_code_0>
        Feedback 0: <feedback_0>
        Answer 1: <SQL_code_1>
        Feedback 1: <feedback_1>
        ...
        Answer k: <SQL_code_n>
        Feedback k: <feedback_n>
        """
        prompt = textwrap.dedent(f"""\
        You are performing the text-to-SQL task. Here is the database schema, user's question, and your previous answer-feedback trajectory.
        
        -- SQL schema: {schema}
        -- User's question: {question}
        -- Your previous answer-feedback trajectory:
        {{trajectory}}
        
        According to the latest feedback, provide your refined SQL code.
        Provide your output in the following format: ```sql\n<refined_SQL_code>\n```""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_shot_template() -> str:
        prompt = textwrap.dedent(f"""\
        Question: {{question}}
        {{answer}}""")
        return prompt

    @staticmethod
    def get_memprompt_template() -> str:
        prompt = textwrap.dedent(f"""\
        Question: {{question}}
        Your SQL code: {{answer}}
        User Feedback: {{correctness}}""")
        return prompt

    def get_fewshot_prompt(self, schema: str, question: str) -> str:
        fewshot_template = self.get_fewshot_template(schema, question)
        return re.sub(pattern=r"\{fewshot_text\}", repl=self.fewshot_text, string=fewshot_template)

    def get_fewshot_text(self) -> str:
        train_rows = self.dataset["train"].shuffle(seed=self.seed)
        shots = list()
        for i in range(self.NUM_SHOTS):
            shot = self.get_shot_template().format(
                question=train_rows[i]["question"],
                answer=train_rows[i]["SQL"]
            )
            shots.append(shot)
        return "\n\n\n".join(shots).replace("\\", "\\\\")

# Manual testing
if __name__ == "__main__":
    DB_ROOT_PATH = "../bird-benchmark/data/bird-benchmark/dev/dev_databases"
    DB_ID = "financial"
    db_path = os.path.join(DB_ROOT_PATH, DB_ID, DB_ID + ".sqlite")
    schema_prompt = generate_schema_prompt(db_path)
    # Test get_zeroshot_prompt
    question = "What is the total amount of money spent on all transactions?"
    zeroshot_prompt = GeneralText2SQL.get_zeroshot_prompt(schema_prompt, question)
    # Test get_fewshot_template
    fewshot_text = "SELECT SUM(amount) FROM transactions"
    fewshot_prompt = GeneralText2SQL.get_fewshot_template(schema_prompt, question).format(fewshot_text=fewshot_text)
    print(fewshot_prompt)
