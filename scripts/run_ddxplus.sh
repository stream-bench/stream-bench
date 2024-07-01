python -m stream_bench.pipelines.run_bench \
    --agent_cfg "configs/agent/mam_stream_icl_cot.yml" \
    --bench_cfg "configs/bench/ddxplus.yml" \
    --entity "photocopier" \
    --use_wandb
