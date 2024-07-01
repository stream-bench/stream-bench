import re
import textwrap
import evaluate
from datasets import Dataset

from stream_bench.benchmarks.base import Bench
from stream_bench.benchmarks.utils import strip_all_lines

class MedicalDiagnosisBench(Bench):
    """A task whose x == patient profile and y == diagnosis."""
    LABEL2TEXT = dict()
    TEXT2LABEL = dict()
    NUM_SHOTS = 16

    def __init__(
        self,
        split: str = "test",
        seed: int = 0,
        feedback: str = "correctness",
        **kwargs
    ) -> None:
        super().__init__({})
        self.split = split
        self.seed = seed
        self.feedback = feedback
        self.option_text = '\n'.join([f"{str(k)}. {v}" for k, v in self.LABEL2TEXT.items()])
        self.fewshot_text = self.get_fewshot_text()

    def get_dataset(self) -> Dataset:
        return self.dataset[self.split].shuffle(seed=self.seed)

    @staticmethod
    def get_zeroshot_prompt(
        profile: str,
        option_text: str
    ) -> str:
        prompt = textwrap.dedent(f"""\
        Act as a medical doctor and diagnose the patient based on the following patient profile:
        
        {profile}
        
        All possible diagnoses for you to choose from are as follows (one diagnosis per line, in the format of <number>. <diagnosis>):
        {option_text}
        
        Now, directly provide the diagnosis for the patient in the following format: <number>. <diagnosis>""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_cot_prompt(
        profile: str,
        option_text: str
    ) -> str:
        prompt = textwrap.dedent(f"""\
        Act as a medical doctor and diagnose the patient based on the following patient profile:
        
        {profile}
        
        All possible diagnoses for you to choose from are as follows (one diagnosis per line, in the format of <number>. <diagnosis>):
        {option_text}
        
        Now, take a deep breath and work on this problem step-by-step to derive the most likely diagnosis.\
        Provide your output in the following valid JSON format: {{"rationale": "<your_rationale>", "answer": "<number>. <diagnosis>"}}""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_shot_template() -> str:
        prompt = textwrap.dedent(f"""\
        {{question}}
        Diagnosis: {{answer}}""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_memprompt_template() -> str:
        prompt = textwrap.dedent(f"""\
        {{question}}
        Your answer: {{answer}}
        User Feedback: {{correctness}}""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_fewshot_template(
        profile: str,
        option_text: str
    ) -> str:
        prompt = textwrap.dedent(f"""\
        Act as a medical doctor and diagnose the patient based on the provided patient profile.
        
        All possible diagnoses for you to choose from are as follows (one diagnosis per line, in the format of <number>. <diagnosis>):
        {option_text}

        Here are some example cases.
        
        {{fewshot_text}}
        
        Now it's your turn.
        
        {profile}        
        
        Now provide the diagnosis for the patient in the following format: <number>. <diagnosis>""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_fewshotcot_template(
        profile: str,
        option_text: str
    ) -> str:
        prompt = textwrap.dedent(f"""\
        Act as a medical doctor and diagnose the patient based on the provided patient profile.
        
        All possible diagnoses for you to choose from are as follows (one diagnosis per line, in the format of <number>. <diagnosis>):
        {option_text}

        Here are some example cases.

        {{fewshot_text}}

        Now it's your turn.

        {profile}

        Now, take a deep breath and work on this problem step-by-step to derive the most likely diagnosis.
        Provide your output in the following valid JSON format: {{"rationale": "<your_rationale>", "answer": "<number>. <diagnosis>"}}""")
        return strip_all_lines(prompt)

    def get_fewshot_prompt(
        self,
        profile: str,
        option_text: str,
    ) -> str:
        fewshot_template = self.get_fewshot_template(profile, option_text)
        return re.sub(r"\{fewshot_text\}", self.fewshot_text, fewshot_template)

    def get_fewshot_text(self) -> str:
        shot_rows = self.dataset["validate"].shuffle(seed=self.seed)
        shots = list()
        for i in range(self.NUM_SHOTS):
            shot = self.get_shot_template().format(
                question=shot_rows[i]["PATIENT_PROFILE"].strip(),
                answer=self.get_label_text(shot_rows[i]["PATHOLOGY"])
            )
            shots.append(shot)
        return "\n\n\n".join(shots).replace("\\", "\\\\")

    @staticmethod
    def get_feedback_template(
        profile: str,
        option_text: str
        ) -> str:
        prompt = textwrap.dedent(f"""\
        You are acting as medical doctor and tasked to diagnose the patient based on the provided patient profile. Here's the patient diagnosis:
        
        {profile}
        
        All possible diagnoses for you to choose from are as follows (one diagnosis per line, in the format of <number>. <diagnosis>):
        {option_text}
        
        Your answer : {{y_hat}}
        First, determine whether you need to refine your answer in terms of its correctness.
        If you consider that your answer is correct, output 'NO NEED TO REFINE' in uppercase.
        Otherwise, provide a suggestion to correct the diagnoses in the format of <number>. <diagnosis>.""")
        return strip_all_lines(prompt)

    @staticmethod
    def get_refine_template(
            profile: str,
            option_text: str
        ) -> str:
        """Note: The format of answer-feedback trajectory should be as follows
        Answer 0: <diagnoses_0>
        Feedback 0: <feedback_0>
        Answer 1: <diagnoses_1>
        Feedback 1: <feedback_1>
        ...
        Answer k: <diagnoses_k>
        Feedback k: <feedback_k>
        """
        prompt = textwrap.dedent(f"""\
        You are acting as medical doctor and tasked to diagnose the patient based on the provided patient profile. Here's the patient diagnosis:
        
        {profile}
        All possible diagnoses for you to choose from are as follows (one diagnosis per line, in the format of <number>. <diagnosis>):
        {option_text}
        -- Your previous answer-feedback trajectory:
        {{trajectory}}
        
        According to the latest feedback, provide your new answer
        Provide your output in the following format: one diagnosis per line, in the format of <number>. <diagnosis>""")
        return strip_all_lines(prompt)

    def get_input(self, row: dict) -> dict:
        row_input = dict()
        profile = row["PATIENT_PROFILE"].strip()
        option_text = self.option_text
        row_input["question"] = profile
        row_input["prompt_zeroshot"] = self.get_zeroshot_prompt(profile, option_text)
        row_input["prompt_fewshot"] = self.get_fewshot_prompt(profile, option_text)
        row_input["prompt_cot"] = self.get_cot_prompt(profile, option_text)
        row_input["fewshot_template"] = self.get_fewshot_template(profile, option_text)
        row_input["fewshotcot_template"] = self.get_fewshotcot_template(profile, option_text)
        row_input["feedback_template"] = self.get_feedback_template(profile, option_text)
        row_input["refine_template"] = self.get_refine_template(profile, option_text)
        return row_input

    def get_output(self, row: dict) -> dict:
        label_text = row["PATHOLOGY"].lower().strip()
        assert label_text in self.TEXT2LABEL
        return self.TEXT2LABEL[label_text]

    def get_metrics(self) -> dict:
        accuracy = evaluate.load("accuracy")
        metrics = accuracy.compute(predictions=self.predictions, references=self.references)
        return metrics        

    def postprocess_generation(self, res: str, idx: int = -1) -> int:
        res = res.lower().strip()
        # Search for the pattern <number>. <diagnosis> using `re`, and extract <number>
        numbers = re.findall(pattern=r"(\d+)\.", string=res)
        if len(numbers) == 1:
            number = int(numbers[0])
            if number in self.LABEL2TEXT:
                prediction = number
            else:
                print(f"Prediction {res} not found in the label set.")
                prediction = self.NOTINLABEL
        else:
            if len(numbers) > 1:
                print(f"Extracted numbers {numbers} is not exactly one. Select the first one.")
                prediction = int(numbers[0])
            else:
                print(f"Prediction {res} has no extracted numbers. Use self.NOTINLABEL")
                prediction = self.NOTINLABEL
        return prediction

    def process_results(
        self,
        prediction: str,
        label: str,
        return_details: bool = False,
        **kwargs
    ) -> bool | dict:
        """Takes the list of LM generations and evaluates them against ground truth references,
        returning the metric for the generations.
        :param generations: list(list(str))
            list of lists containing generations
        :param labels: original labels
            list of str containing refrences
        """
        accuracy = evaluate.load("accuracy")
        correct = prediction == label
        self.n_correct += correct
        self.predictions.append(prediction)
        self.references.append(label)
        rolling_acc = accuracy.compute(predictions=self.predictions,
                                       references=self.references)["accuracy"]

        if return_details:
            return {
                'correct': int(correct),
                'n_correct': self.n_correct,
                'rolling_acc': rolling_acc
            }
        return correct

    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        pred_int = self.postprocess_generation(model_output)
        has_feedback = True
        feedbacks = {
            "question": row["PATIENT_PROFILE"].strip(),
            "self_output": self.get_label_text(pred_int),
            "is_correct": res["correct"],
            "ground_truth": self.get_label_text(row["PATHOLOGY"]),
            "shot_template": self.get_shot_template(),
            "memprompt_template": self.get_memprompt_template()
        }
        return has_feedback, feedbacks

    def get_label_text(self, label: int | str) -> str:
        label_int = self.NOTINLABEL
        label_str = "I'm not confident about the diagnosis."
        if isinstance(label, int) and (label in self.LABEL2TEXT):
            label_int = label
            label_str = self.LABEL2TEXT[label_int]
        elif isinstance(label, str) and (label.lower() in self.TEXT2LABEL):
            label_int = self.TEXT2LABEL[label.lower()]
            label_str = label
        return f"{label_int}. {label_str}"

def create_ddxplus():
    class DDXPlusBench(MedicalDiagnosisBench):
        DATASET_PATH = "appier-ai-research/StreamBench"
        DATASET_NAME = "ddxplus"
        
        LABEL2TEXT = {
            0: 'Acute COPD exacerbation / infection',
            1: 'Acute dystonic reactions',
            2: 'Acute laryngitis',
            3: 'Acute otitis media',
            4: 'Acute pulmonary edema',
            5: 'Acute rhinosinusitis',
            6: 'Allergic sinusitis',
            7: 'Anaphylaxis',
            8: 'Anemia',
            9: 'Atrial fibrillation',
            10: 'Boerhaave',
            11: 'Bronchiectasis',
            12: 'Bronchiolitis',
            13: 'Bronchitis',
            14: 'Bronchospasm / acute asthma exacerbation',
            15: 'Chagas',
            16: 'Chronic rhinosinusitis',
            17: 'Cluster headache',
            18: 'Croup',
            19: 'Ebola',
            20: 'Epiglottitis',
            21: 'GERD',
            22: 'Guillain-Barré syndrome',
            23: 'HIV (initial infection)',
            24: 'Influenza',
            25: 'Inguinal hernia',
            26: 'Larygospasm',
            27: 'Localized edema',
            28: 'Myasthenia gravis',
            29: 'Myocarditis',
            30: 'PSVT',
            31: 'Pancreatic neoplasm',
            32: 'Panic attack',
            33: 'Pericarditis',
            34: 'Pneumonia',
            35: 'Possible NSTEMI / STEMI',
            36: 'Pulmonary embolism',
            37: 'Pulmonary neoplasm',
            38: 'SLE',
            39: 'Sarcoidosis',
            40: 'Scombroid food poisoning',
            41: 'Spontaneous pneumothorax',
            42: 'Spontaneous rib fracture',
            43: 'Stable angina',
            44: 'Tuberculosis',
            45: 'URTI',
            46: 'Unstable angina',
            47: 'Viral pharyngitis',
            48: 'Whooping cough'
        }
        NOTINLABEL = len(LABEL2TEXT)
        TEXT2LABEL = {v.lower(): k for k, v in LABEL2TEXT.items()}
        LABEL_SET = {v.lower() for v in LABEL2TEXT.values()}

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    return DDXPlusBench
