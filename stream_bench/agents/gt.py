from stream_bench.agents.base import Agent

class GroundTruthAgent(Agent):

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def __call__(
        self,
        question: str,
        label_text: str,
        **kwargs
    ) -> str:
        self.reset_log_info()
        self.update_log_info(log_data={
            "input_pred": question,
            "output_pred": label_text,
            "num_input_tokens": len(question) // 4,  # approximation
            "num_output_tokens": len(label_text) // 4  # approximation
        })
        return label_text

    def update(self, has_feedback: bool, **feedbacks) -> bool:        
        return False  # ground truth agent doesn't need to be updated

    def get_name(self) -> str:
        return self.__class__.__name__
