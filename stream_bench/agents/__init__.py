from .zeroshot import ZeroShotAgent
from .fewshot import FewShotAgent
from .cot import CoTAgent
from .iter_prompt import IterPromptAgent
from .scratchpad import ScratchPadAgent
from .fewshot_rag import FewShotRAGAgent
from .multiagent_rag import MultiAgent
from .gt import GroundTruthAgent

classes = locals()

TASKS = {
    "zeroshot": ZeroShotAgent,
    "fewshot": FewShotAgent,
    "cot": CoTAgent,
    "self_refine": IterPromptAgent,
    "grow_prompt": ScratchPadAgent,
    "mem_prompt": FewShotRAGAgent,
    "self_stream_icl": FewShotRAGAgent,
    "self_stream_icl_cot": FewShotRAGAgent,
    "ma_rr": MultiAgent,
    "ma_rr_cot": MultiAgent,
    "gt": GroundTruthAgent
}

def load_agent(agent_name):
    if agent_name in TASKS:
        return TASKS[agent_name]
    if agent_name in classes:
        return classes[agent_name]

    raise ValueError("Agent %s not found" % agent_name)
