python -m stream_bench.pipelines.run_bench_batch \
    --agent_cfg "configs/agent/cot.yml" \
    --bench_cfg "configs/bench/math.yml" \
    --entity "photocopier" \
    --use_wandb
