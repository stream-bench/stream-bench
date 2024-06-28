from .base import Bench
from .ddxplus import create_ddxplus
from .ds_1000 import DS1000
classes = locals()

TASKS = {
    "ddxplus": create_ddxplus(),
    "ds_1000": DS1000
}

def load_benchmark(benchmark_name) -> Bench:
    if benchmark_name in TASKS:
        return TASKS[benchmark_name]
    if benchmark_name in classes:
        return classes[benchmark_name]

    raise ValueError("Benchmark %s not found" % benchmark_name)
