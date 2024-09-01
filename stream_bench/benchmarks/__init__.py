from .base import Bench
from .ddxplus import create_ddxplus
from .ds_1000 import DS1000
from .hotpotqa_distract import HotpotQADistract
from .toolbench import ToolBench
from .gsm8k import GSM8KBench
from .math import MATHBench
from .text_to_sql import create_bird, create_cosql, create_spider

classes = locals()

TASKS = {
    "ddxplus": create_ddxplus(),
    "ds_1000": DS1000,
    "hotpotqa_distract": HotpotQADistract,
    "toolbench": ToolBench,
    "gsm8k": GSM8KBench,
    "math": MATHBench,
    "bird": create_bird(),
    "cosql": create_cosql(),
    "spider": create_spider(),
}

def load_benchmark(benchmark_name) -> Bench:
    if benchmark_name in TASKS:
        return TASKS[benchmark_name]
    if benchmark_name in classes:
        return classes[benchmark_name]

    raise ValueError("Benchmark %s not found" % benchmark_name)
