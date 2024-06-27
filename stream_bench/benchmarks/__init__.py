from .base import Bench
from .ddxplus import create_ddxplus
classes = locals()

TASKS = {
    'ddxplus': create_ddxplus()
}

def load_benchmark(benchmark_name) -> Bench:
    if benchmark_name in TASKS:
        return TASKS[benchmark_name]
    if benchmark_name in classes:
        return classes[benchmark_name]

    raise ValueError("Benchmark %s not found" % benchmark_name)
