import json
import textwrap

from .utils import get_llm, setup_logger

# The base class used for classification and multi-choice questions (MCQs)
class Agent:
    LOG_KEYS = [
        "num_inference_call",  # number of inference call to the LLM
        "num_success_call",  # (per-call-level) whether the inference / API call is successful
        "num_input_tokens",  # the total number of input tokens in __call__()
        "num_output_tokens",  # the total number of output tokens in __call__()
    ]
    # Prompt for parsing the outputs for mapping to the label space
    PROMPT_PARSE = textwrap.dedent(f"""\
    Model output: {{model_output}}
    
    Convert the model output into one of the following options (one option per line):
    {{options}}
    
    Answer (please only answer with a single option):""")

    def __init__(self, config: dict) -> None:
        self.config = config
        self.llm_config = config["llm"]
        self.llm = get_llm(series=self.llm_config["series"], model_name=self.llm_config["model_name"])
        # Setup logging info
        self.exp_name = config["exp_name"] if "exp_name" in config else self.get_name()
        self.log_path = f'log/{config["bench_name"]}/{config["split"]}/{self.exp_name}.jsonl'
        self.logger = setup_logger(name="jsonlines_logger", log_file=self.log_path)
        self.log_info = {KEY: 0 for KEY in self.LOG_KEYS}  # log information of the current data point
        self.accum_log_info = {KEY: 0 for KEY in self.LOG_KEYS}  # accum_log_info: accumulation of self.log_info through time steps

    def __call__(self, prompt: str, label_set: list[str], **kwargs) -> str:
        """Generate response text using the prompt. The response should be parsed to a label in the label_set."""
        raise NotImplementedError

    def initialize(self, train_rows: list[dict]) -> None:
        """(Optional) Initialize the agent with some training instances.

        The training instances should be a list of dictionaries, each of which should at least contain the following keys:
        {"desc": <str>, "input": <str>, "output": <str>, "label_set": <set>}

        "desc": The task description (invariant across each instance, e.g., Based on the premise and hypothesis provided, determine the relationship between them. Choose the appropriate answer from the following options (one option per line):\nentailment\nneutral\ncontradiction)
        "x": The training input
        "y": The verbalized label of this instance
        "label_set": All possible labels
        """
        assert isinstance(train_rows, list)
        keys = ["desc", "x", "y", "label_set"]
        for train_row in train_rows:
            assert isinstance(train_row, dict)
            for key in keys:
                assert key in train_row

    def update(self, has_feedback: bool, **feedbacks) -> bool:
        """Return True if the agent is updated in this time_step."""
        raise NotImplementedError

    def get_name(self) -> str:
        return f'{self.__class__.__name__}__{self.llm_config["series"]}__{self.llm_config["model_name"].split("/")[-1]}'

    def reset_log_info(self) -> None:
        self.log_info = {KEY: 0 for KEY in self.LOG_KEYS}

    def update_log_info(self, log_data: dict) -> None:
        for k, v in log_data.items():
            if isinstance(v, str) or isinstance(v, list):
                self.log_info[k] = v
            elif isinstance(v, int):
                self.log_info[k] += v
                if k in self.accum_log_info.keys():
                    self.accum_log_info[k] += v
            else:
                raise ValueError(f"error key-value pair: {k} -> {v} ({v} should be either str, int, or list)")

    def get_wandb_log_info(self) -> dict:
        log_data = dict()
        for key in self.LOG_KEYS:
            log_data[key] = self.log_info[key]
            log_data[f"total_{key}"] = self.accum_log_info[key]
        return log_data

    def log(self, label_text: str = None) -> None:
        """This method should be called at the end of each time_step."""
        self.log_info["label_text"] = label_text
        self.logger.info(json.dumps(self.log_info))
        self.reset_log_info()

    def get_options_text(self, label_set: set[str]) -> str:
        """Convert the label_set into the option text."""
        return '\n'.join(list(label_set))
