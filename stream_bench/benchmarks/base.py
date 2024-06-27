import random
import evaluate
import textwrap
from abc import ABC, abstractmethod
from typing import Any
from datasets import load_dataset, Dataset

class Bench(ABC):
    """Associated with corresponding Dataset, Feedback, and Metrics"""
    DATASET_PATH: str = None
    DATASET_NAME: str = None

    def __init__(self, config: dict):
        self.config = config
        self.dataset = load_dataset(self.DATASET_PATH, self.DATASET_NAME)
        self.use_wandb = False
        self.n_correct = 0
        self.references = []
        self.predictions = []

    @abstractmethod
    def get_dataset(self) -> Dataset:
        raise NotImplementedError

    @abstractmethod
    def give_feedback(self, model_output: str, row: dict, res: dict) -> tuple[bool, dict]:
        """Give feedback according to benchmark configurations.

        1. No feedback
        2. Weak feedback (True: correct, False: incorrect)
        3. Strong feedback (Ground truth string)
        """
        raise NotImplementedError

    @abstractmethod
    def get_input(self, row: dict) -> dict:
        """
        return must include prompt field of string value
        """
        raise NotImplementedError

    @abstractmethod
    def get_output(self, row: dict) -> dict:
        """Extract the label of the row (instance)."""
        raise NotImplementedError

    @abstractmethod
    def get_metrics(self) -> dict:
        """Calculate and return the metrics for this benchmark."""
        raise NotImplementedError

    @abstractmethod
    def postprocess_generation(self, res: Any, idx: int) -> Any:
        """Postprocess the agent's response and map it to the label space.

        Args:
            res (Any): the agent's response
            idx (int): the instance's index in the dataset

        Returns:
            Any: the predicted label
        """
        raise NotImplementedError

    @abstractmethod
    def process_results(self, prediction: Any, label: Any, return_details: bool = False) -> bool | dict:
        """Compare the prediction with the label and calculate streaming metrics at the current time point.

        Args:
            prediction (Any): the agent's prediction
            label (Any): the ground truth label
            return_details (bool, optional): Return correctness of prediction (bool) or detailed metrics (dict). Defaults to False

        Returns:
            bool | dict:  Return correctness of prediction (bool) or detailed metrics (dict)
        """
        raise NotImplementedError
