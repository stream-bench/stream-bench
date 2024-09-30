import re
import json
from datasets import Dataset
from colorama import Fore, Style

from stream_bench.llms.oai_chat import OpenAIChat
from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.utils import strip_all_lines, extract_json_string

EQUALITY_TEMPLATE = r"""
Look at the following two expressions (answers to a math problem) and judge whether they are equivalent. Only perform trivial simplifications

Examples:

    Expression 1: $2x+3$
    Expression 2: $3+2x$

Yes

    Expression 1: 3/2
    Expression 2: 1.5

Yes

    Expression 1: $x^2+2x+1$
    Expression 2: $y^2+2y+1$

No

    Expression 1: $x^2+2x+1$
    Expression 2: $(x+1)^2$

Yes

    Expression 1: 3245/5
    Expression 2: 649

No
(these are actually equal, don't mark them equivalent if you need to do nontrivial simplifications)

    Expression 1: 2/(-3)
    Expression 2: -2/3

Yes
(trivial simplifications are allowed)

    Expression 1: 72 degrees
    Expression 2: 72

Yes
(give benefit of the doubt to units)

    Expression 1: 64
    Expression 2: 64 square feet

Yes
(give benefit of the doubt to units)

---

YOUR TASK


Respond with only "Yes" or "No" (without quotes). Do not include a rationale.

    Expression 1: %(expression1)s
    Expression 2: %(expression2)s
""".strip()

class MATHBench(Bench):
    """Benchmark for the GSM8K dataset."""
    DATASET_PATH = "appier-ai-research/robust-finetuning"
    DATASET_NAME = "math-resample"
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
        self.llm = OpenAIChat(model_name=self.EVAL_LLM)
        self.answer_extraction = kwargs.get("answer_extraction", "answer")

    def get_dataset(self) -> Dataset:
        return self.dataset[self.split].shuffle(seed=self.seed)

    @staticmethod
    def get_zeroshot_prompt(question: str) -> str:
        return question

    @staticmethod
    def get_cot_prompt(question: str) -> str:
        prompt = f"""\
        Solve the following math problem step by step. The last line of your response should be of the form Answer: $ANSWER (without quotes) where $ANSWER is the answer to the problem.

        {question}

        Remember to put your answer on its own line after "Answer:", and you do not need to use a \\boxed command."""
        return strip_all_lines(prompt)

    @staticmethod
    def get_cot_json_prompt(question: str) -> str:
        prompt = f"""\
        Solve the following math problem step by step before providing your answer.

        {question}

        Provide your output in the following JSON format:
        ```json
        {{"reasoning": <your reasoning>, "answer": <your answer>}}
        ```"""
        return strip_all_lines(prompt)

    def get_input(self, row: dict) -> dict:
        row_input = dict()
        row_input["question"] = row["problem"]
        row_input["prompt_zeroshot"] = self.get_zeroshot_prompt(row["problem"])
        row_input["prompt_cot"] = self.get_cot_prompt(row["problem"])
        row_input["prompt_cot_json"] = self.get_cot_json_prompt(row["problem"])
        return row_input

    def get_output(self, row: dict) -> str:
        return self.math_normalizer(row["solution"])

    def check_equality(self, pred: str, ref: str) -> bool:
        prompt = EQUALITY_TEMPLATE % {"expression1": pred, "expression2": ref}
        res, _ = self.llm(prompt, max_tokens=32)
        return res.lower().strip() == "yes"

    def get_metrics(self) -> dict:
        return {"accuracy": self.n_correct / len(self.predictions)}

    def postprocess_generation(self, res: str, idx: int = -1) -> str:
        if self.answer_extraction == "answer":
            ANSWER_PATTERN = r"(?i)Answer\s*:\s*([^\n]+)"
            ans_match = re.search(ANSWER_PATTERN, res)
            extracted_answer = ans_match.group(1) if ans_match else "Answer not found"
        elif self.answer_extraction == "boxed":
            extracted_answer = self.math_normalizer(res)
        elif self.answer_extraction == "json":
            json_str = extract_json_string(res)
            try:
                json_obj = json.loads(json_str)
                if "answer" in json_obj:
                    extracted_answer = json_obj["answer"]
                else:
                    print(Fore.RED + f"Answer not found in the JSON object" + Style.RESET_ALL)
                    extracted_answer = res
            except json.JSONDecodeError:
                print(Fore.RED + f"JSONDecodeError: failed to extract answer" + Style.RESET_ALL)
                extracted_answer = res
        return extracted_answer

    def process_results(
        self,
        prediction: str,
        label: str,
        return_details: bool = True,
        **kwargs
    ) -> bool | dict:
        correct = float(self.check_equality(prediction, label))
        self.n_correct += correct
        self.predictions.append(prediction)
        self.references.append(label)
        if return_details:
            return {
                "correct": int(correct),
                "n_correct": self.n_correct,
                "rolling_acc": self.n_correct / len(self.predictions)
            }
        return bool(correct)

    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        return True, {}

    @staticmethod
    def math_normalizer(text: str) -> str:  # noqa C901
        """Source: https://github.com/hendrycks/math"""

        def _remove_boxed(text: str | None) -> str:
            """
            Extract the text within a \\boxed{...} environment.
            Example:
            >>> _remove_boxed(\\boxed{\\frac{2}{3}})
            \\frac{2}{3}
            """
            if text is None:
                return ""
            if "\\boxed " in text:
                left = "\\boxed "
                assert text[: len(left)] == left
                return text[len(left) :]

            left = "\\boxed{"

            assert text[: len(left)] == left
            assert text[-1] == "}"

            return text[len(left) : -1]

        def _last_boxed_only_string(text: str) -> str | None:
            """Extract the last \\boxed{...} or \\fbox{...} element from a string."""
            idx = text.rfind("\\boxed")
            if idx < 0:
                idx = text.rfind("\\fbox")
                if idx < 0:
                    return None

            i = idx
            right_brace_idx = None
            num_left_braces_open = 0
            while i < len(text):
                if text[i] == "{":
                    num_left_braces_open += 1
                if text[i] == "}":
                    num_left_braces_open -= 1
                    if num_left_braces_open == 0:
                        right_brace_idx = i
                        break
                i += 1

            if right_brace_idx is None:
                retval = None
            else:
                retval = text[idx : right_brace_idx + 1]

            return retval

        def _fix_fracs(text: str) -> str:
            """
            Fix the formatting of fractions in the given text.
            Copied from: https://github.com/hendrycks/math/blob/357963a7f5501a6c1708cf3f3fb0cdf525642761/modeling/math_equivalence.py#L1

            Args:
                text (str): The input text.

            Returns:
                str: The text with properly formatted fractions.

            Examples:
                >>> _fix_fracs("\\frac12")
                "\\frac{1}{2}"
                >>> _fix_fracs("\\frac{3}{4}")
                "\\frac{3}{4}"
                >>> _fix_fracs("\\frac1{2}")
                "\\frac{1}{2}"
            """
            substrs = text.split("\\frac")
            new_str = substrs[0]
            if len(substrs) > 1:
                substrs = substrs[1:]
                for substr in substrs:
                    new_str += "\\frac"
                    if substr[0] == "{":
                        new_str += substr
                    else:
                        try:
                            assert len(substr) >= 2
                        except AssertionError:
                            return text
                        a = substr[0]
                        b = substr[1]
                        if b != "{":
                            if len(substr) > 2:
                                post_substr = substr[2:]
                                new_str += "{" + a + "}{" + b + "}" + post_substr
                            else:
                                new_str += "{" + a + "}{" + b + "}"
                        else:
                            if len(substr) > 2:
                                post_substr = substr[2:]
                                new_str += "{" + a + "}" + b + post_substr
                            else:
                                new_str += "{" + a + "}" + b
            text = new_str
            return text

        def _fix_a_slash_b(text: str) -> str:
            """Source: https://github.com/hendrycks/math
            Reformat fractions formatted as a/b to \\frac{a}{b}.
            Example:
            >>> _fix_a_slash_b("2/3")
            \frac{2}{3}
            """
            if len(text.split("/")) != 2:
                return text
            a_str = text.split("/")[0]
            b_str = text.split("/")[1]
            try:
                a = int(a_str)
                b = int(b_str)
                assert text == "{}/{}".format(a, b)
                new_string = "\\frac{" + str(a) + "}{" + str(b) + "}"
                return new_string
            except Exception:
                return text

        def _remove_right_units(text: str) -> str:
            """
            Removes unit descriptions from LaTeX-formatted text, where units are indicated by "\\text{ }".
            This function splits the text at each "\\text{ " and returns the part before the first occurrence,
            effectively discarding any units and additional text following this pattern. This function also
            trims any trailing whitespace left after removing units.

            Args:
                text (str): The input string potentially containing LaTeX-style unit descriptions.

            Returns:
                str: The text with unit descriptions removed.

            Examples:
                - Input: '50.5 \\text{ kg}'
                Output: '50.5'

                - Input: 'The mass is 20 grams'
                Output: 'The mass is 20 grams'

                - Input: 'The object weighs 30.2 \\text{ lbs} and is 15 \\text{ inches} long'
                Output: 'The object weighs 30.2'

                - Input: '\\text{ unit without preceding text}'
                Output: ''

            Note:
                This function assumes that "\\text{ " is only used to denote units. It will remove all text
                following the first occurrence of "\\text{ ", including any further text and units that might
                appear in complex sentences.
            """
            # Check for "\\text{ " and split the text at each occurrence
            if "\\text{ " in text:
                splits = text.split("\\text{ ")
                # Return only the first part which is assumed to contain the main content without units
                return splits[0].rstrip()
            else:
                return text

        def _fix_sqrt(text: str) -> str:
            """Source: https://github.com/hendrycks/math
            Reformat square roots.
            Example:
            >>> _fix_sqrt("\\sqrt3")
            \\sqrt{3}
            """
            if "\\sqrt" not in text:
                return text
            splits = text.split("\\sqrt")
            new_string = splits[0]
            for split in splits[1:]:
                if split[0] != "{":
                    a = split[0]
                    new_substr = "\\sqrt{" + a + "}" + split[1:]
                else:
                    new_substr = "\\sqrt" + split
                new_string += new_substr
            return new_string

        text = _remove_boxed(_last_boxed_only_string(text))

        to_replace_1 = [
            ("\n", ""),  # linebreaks
            ("\\!", ""),  # remove inverse spaces
            ("\\\\", "\\"),  # replace \\ with \
            ("tfrac", "frac"),  # replace tfrac and dfrac with frac
            ("dfrac", "frac"),
            ("\\left", ""),  # remove \left and \right
            ("\\right", ""),
            ("^{\\circ}", ""),  # Remove circ (degrees)
            ("^\\circ", ""),
            ("\\$", ""),  # remove dollar signs
        ]

        for input_str, output_str in to_replace_1:
            text = text.replace(input_str, output_str)

        # remove units (on the right)
        text = _remove_right_units(text)

        to_replace_2 = [
            ("\\%", ""),  # remove percentage
            (r"\%", ""),
            (
                " .",
                " 0.",
            ),  # " 0." equivalent to " ." and "{0." equivalent to "{." Alternatively, add "0" if "." is the start of the text
            ("{.", "{0."),
        ]
        for input_str, output_str in to_replace_2:
            text = text.replace(input_str, output_str)

        # if empty, return empty text
        if len(text) == 0:
            return text
        if text[0] == ".":
            text = "0" + text

        # to consider: get rid of e.g. "k = " or "q = " at beginning
        if len(text.split("=")) == 2:
            if len(text.split("=")[0]) <= 2:
                text = text.split("=")[1]

        # fix sqrt3 --> sqrt{3}
        text = _fix_sqrt(text)

        # remove spaces
        text = text.replace(" ", "")

        # \frac1b or \frac12 --> \frac{1}{b} and \frac{1}{2}, etc. Even works with \frac1{72} (but not \frac{72}1). Also does a/b --> \\frac{a}{b}
        text = _fix_fracs(text)

        # manually change 0.5 --> \frac{1}{2}
        if text == "0.5":
            text = "\\frac{1}{2}"

        # NOTE: X/Y changed to \frac{X}{Y} in dataset, but in simple cases fix in case the model output is X/Y
        text = _fix_a_slash_b(text)

        return text

if __name__ == "__main__":
    q = "..."
    print(MATHBench.get_cot_json_prompt(q))
