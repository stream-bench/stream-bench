import re
import copy
import textwrap
import warnings
warnings.filterwarnings("default")

from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.utils import strip_all_lines
from stream_bench.benchmarks.ds1000_utils import execution, fewshots

four_space_tab = "    "

def fix_tab_indents(text: str) -> str:
    return text.replace("\t", four_space_tab)

def extract_code(text):
    pattern = r'```(?:python)?\s*(.*?)```?'
    code_blocks = re.findall(pattern, text, re.DOTALL)
    return code_blocks


class DS1000(Bench):
    """A task represents an entire benchmark including its dataset, problems,
    answers, generation settings and evaluation methods.
    """
    DATASET_PATH = "appier-ai-research/StreamBench"
    DATASET_NAME = "ds_1000"
    FEWSHOTS = fewshots.rows

    def __init__(
        self,
        split: str = "test",
        seed: int = 0,
        feedback: str = "correctness",
        timeout=3.0,
        agent=None,
        mode='instruct',
        **kwargs
    ) -> None:
        super().__init__(config={})
        assert mode in ['instruct', 'write','replit-glaive','standard']
        # outsource this to yaml attribute
        self.split = split
        self.seed = seed
        self.feedback = feedback
        self.total = 0
        self.correct_stats = {lib: [] for lib in ['Pytorch', 'Tensorflow', 'Pandas', 'Numpy', 'Matplotlib', 'Sklearn', 'Scipy']}
        self.timeout = timeout
        self.agent_callback = None
        if hasattr(agent, 'retrieve_experience'):
            self.agent_callback = agent.retrieve_experience
        self.fewshot_text = self.get_fewshot_text()

    def get_dataset(self):
        """Returns dataset for the task or an iterable of any object, that get_prompt can handle"""
        return self.dataset[self.split].shuffle(seed=self.seed)

    # Next, I would like to refactor the following code to be like the class GeneralText2SQL
    @staticmethod
    def get_zeroshot_prompt(
        question: str,
        exec_context: str
    ) -> str:
        prompt = textwrap.dedent(f"""\
        Here is the user's requirements for solving a programming problem (enclosed in '''):
        '''
        {question}
        '''
        
        You need to provide your solution in python code to satisfy the user's requirements. Your code will be tested as follows (enclosed in '''):
        '''
        {exec_context}
        
        code = exec_context.replace("[insert]", <your_code>)
        a_test_case = generate_test_case()
        test_input, expected_result = a_test_case
        test_env = {{"test_input": test_input}}
        exec(code, test_env)
        assertEqual(test_env["result"], expected_result)
        '''
        
        Now, generate your code directly in the following format:
        ```python
        <your_code>
        ```""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_cot_prompt(
        question: str,
        exec_context: str
    ) -> str:
        prompt = textwrap.dedent(f"""\
        Here is the user's requirements for solving a programming problem (enclosed in '''):
        '''
        {question}
        '''
        
        You need to provide your solution in python code to satisfy the user's requirements. Your code will be tested as follows (enclosed in '''):
        '''
        {exec_context}
        
        code = exec_context.replace("[insert]", <your_code>)
        a_test_case = generate_test_case()
        test_input, expected_result = a_test_case
        test_env = {{"test_input": test_input}}
        exec(code, test_env)
        assertEqual(test_env["result"], expected_result)
        '''
        
        Now, take a deep breath and work on this problem step-by-step to derive the correct python code.
        Provide your output in the following format:
        Raionale: <your_rationale>
        Answer: ```python
        <your_code>
        ```""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_shot_template() -> str:
        prompt = textwrap.dedent(f"""\
        The user's requirements:
        '''
        {{question}}
        '''
        Your solution in python code:
        ```python
        {{answer}}
        ```""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_memprompt_template() -> str:
        prompt = textwrap.dedent(f"""\
        The user's requirements:
        '''
        {{question}}
        '''
        Your solution in python code:
        ```python
        {{answer}}
        ```
        User Feedback: {{correctness}}""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_fewshot_template(
        question: str,
        exec_context: str
    ) -> str:
        prompt = textwrap.dedent(f"""\
        You are performing a python programming task to satisfy the user's requirements. Here are some examples:
        
        {{fewshot_text}}
        
        Now it's your turn.
        
        The user's requirements:
        '''
        {question}
        '''
        
        You need to provide your solution in python code to satisfy the user's requirements. Your code will be tested as follows (enclosed in '''):
        '''
        {exec_context}
        
        code = exec_context.replace("[insert]", <your_code>)
        a_test_case = generate_test_case()
        test_input, expected_result = a_test_case
        test_env = {{"test_input": test_input}}
        exec(code, test_env)
        assertEqual(test_env["result"], expected_result)
        '''
        
        Now, generate your code directly in the following format:
        ```python
        <your_code>
        ```""")
        return strip_all_lines(prompt)

    def get_fewshot_prompt(
        self,
        question: str,
        exec_context: str
    ) -> str:
        fewshot_template = self.get_fewshot_template(question=question, exec_context=exec_context)
        return re.sub(pattern=r"\{fewshot_text\}", repl=self.fewshot_text, string=fewshot_template)

    def get_fewshot_text(self) -> str:
        assert len(self.FEWSHOTS) == 4
        shots = list()
        for row in self.FEWSHOTS:
            shot = self.get_shot_template().format(
                question=row["prompt"].strip(),
                answer=row["reference_code"]
            )
            shots.append(shot)
        return "\n\n\n".join(shots).replace("\\", "\\\\")

    def get_input(self, row: dict) -> dict:
        """Builds the prompt for the LM to generate from."""
        exec_context = self.extract_after_exec_content(row["code_context"])
        row_input = copy.deepcopy(row)
        row_input["question"] = row["prompt"].strip()
        row_input["label_text"] = row["reference_code"]
        row_input["prompt_zeroshot"] = self.get_zeroshot_prompt(question=row_input["question"], exec_context=exec_context)
        row_input["prompt_fewshot"] = self.get_fewshot_prompt(question=row_input["question"], exec_context=exec_context)
        row_input["prompt_cot"] = self.get_cot_prompt(question=row_input["question"], exec_context=exec_context)
        row_input["fewshot_template"] = self.get_fewshot_template(question=row_input["question"], exec_context=exec_context)
        row_input["feedback_template"] = self.get_feedback_template(question=row_input["question"], exec_context=exec_context)
        row_input["refine_template"] = self.get_refine_template(question=row_input["question"], exec_context=exec_context)
        return row_input

    # STEP 2
    def postprocess_generation(self, generation: str, idx: int = -1) -> str:
        """Defines the postprocessing for a LM generation.
        :param generation: str
            code generation from LM
        :param idx: int
            index of doc in the dataset to which the generation belongs
            (not used for Humaneval-Task)
        """
        try:
            match = re.search(
                pattern=r"```python(.*?)```",
                string=generation,
                flags=re.DOTALL
            ).group(1)
        except Exception as e:
            match = generation
        return match

    # STEP 3
    def get_output(self, doc):
        return {
            'label': doc['reference_code'],
            'problem_id' : int(doc['metadata']['problem_id']),
            'lib' : doc['metadata']['library'],
            'code_context': doc['code_context']
        }

    # STEP 4
    def process_results(self, generations, references, return_details=False, simulate_env=False,**kwargs):
        """Takes the list of LM generations and evaluates them against ground truth references,
        returning the metric for the generations.
        :param generations: list(list(str))
            list of lists containing generations
        :param references: list(str)
            list of str containing refrences
        """
        code_context = references['code_context']
        prediction = generations
        completion_id = references['problem_id']
        lib = references['lib']
        test_program = (
            "import matplotlib\nmatplotlib.use('agg')\n" + code_context + '\n'
            + f'code = {repr(prediction)}\n'
            + 'test_execution(code)\n'
            + ('test_string(code)\n'  if 'test_string(' in code_context  else '\n')
        )
        results = execution.check_correctness(
            test_program,
            timeout=self.timeout,
            completion_id=completion_id
        )
        correct = results['passed']

        if not simulate_env:
            self.correct_stats[lib].append(int(correct))
            self.n_correct += int(correct)
            self.predictions.append(generations)
            self.references.append(references)
            self.total += 1
        rolling_acc = self.n_correct / max(self.total, 1)

        if return_details:
            stats = {}
            for lib, correct_counts in self.correct_stats.items():
                stats[lib] = sum(correct_counts)/max(len(correct_counts), 1)
            return {
                'correct': correct,
                'n_correct': self.n_correct,
                'rolling_acc': rolling_acc,
                **stats,
                **results
            }
        return correct

    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        pred_str = self.postprocess_generation(model_output)
        has_feedback = True
        feedbacks = {
            "question": row["prompt"].strip(),
            "self_output": pred_str,
            "is_correct": res["correct"],
            "ground_truth": row["reference_code"],
            "shot_template": self.get_shot_template(),
            "memprompt_template": self.get_memprompt_template()
        }
        return has_feedback, feedbacks

    def get_reference(self, doc):
        """Builds the reference solution for the doc (sample from the test dataset)."""
        test_func = doc["test"]
        entry_point = f"check({doc['entry_point']})"
        return "\n" + test_func + "\n" + entry_point

    def get_metrics(self):
        return {
            'pass@1': self.n_correct / self.total
        }

    def get_question_text(self, row):
        return row['raw_prompt']['prompt']

    def get_answer_text(self, row):
        return row["reference_code"]

    def get_choices_text(self, row):
        return ''

    @staticmethod
    def extract_after_exec_content(code_context: str) -> str:
        return re.findall(pattern=r'exec_context.*"""', string=code_context, flags=re.DOTALL)

    @staticmethod
    def get_feedback_template(question: str, exec_context: str) -> str:
        prompt = textwrap.dedent(f"""\
        Here is the user's requirements for solving a programming problem (enclosed in '''):
        '''
        {question}
        '''
        You need to provide your solution in python code to satisfy the user's requirements. Your code will be tested as follows (enclosed in '''):
        '''
        {exec_context}
        code = exec_context.replace("[insert]", <your_code>)
        a_test_case = generate_test_case()
        test_input, expected_result = a_test_case
        test_env = {{"test_input": test_input}}
        exec(code, test_env)
        assertEqual(test_env["result"], expected_result)
        '''
        Here is your previously generated code:
        ```python
        {{y_hat}}
        ```
        First, determine whether you need to refine your code in terms of its correctness.
        If you consider that your code is correct, output 'NO NEED TO REFINE' in uppercase.
        Otherwise, provide a suggestion to correct the code.""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_refine_template(question: str, exec_context: str) -> str:
        """Note: The format of answer-feedback trajectory should be as follows
        Answer 0: <code_0>
        Feedback 0: <feedback_0>
        Answer 1: <code_1>
        Feedback 1: <feedback_1>
        ...
        Answer k: <code_n>
        Feedback k: <feedback_n>
        """
        prompt = textwrap.dedent(f"""\
        Here is the user's requirements for solving a programming problem (enclosed in '''):
        '''
        {question}
        '''
        You need to provide your solution in python code to satisfy the user's requirements. Your code will be tested as follows (enclosed in '''):
        '''
        {exec_context}
        code = exec_context.replace("[insert]", <your_code>)
        a_test_case = generate_test_case()
        test_input, expected_result = a_test_case
        test_env = {{"test_input": test_input}}
        exec(code, test_env)
        assertEqual(test_env["result"], expected_result)
        '''
        Here is your previous answer-feedback trajectory:
        {{trajectory}}
        According to the latest feedback, provide your refined code.
        Provide your output in the following format: ```python\n<refined_code>\n```""")
        return strip_all_lines(prompt)
