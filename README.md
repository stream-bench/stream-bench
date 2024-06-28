# StreamBench: Towards Benchmarking Continuous Improvement of Language Agents

**TL;DR:** We propose a pioneering benchmark to evaluate LLM agents' ability to improve over time in streaming scenarios

**Paper link:** https://arxiv.org/abs/2406.08747

**Note:** Work in progress. Feel free to leave github issues / pull requests if you encounter any issues!

## Steps to Reproduce the Experiments
**Note:** Currently only the baselines on the `DDXPlus` dataset is implemented. We are refactoring the code for other baselines and datasets. Stay tuned!

### Install Required Packages
Run the following commands to install the requirements:
```
conda create -n stream_bench python=3.10
conda activate stream_bench
python -m pip install -r requirements.txt
```

### Setup Environment Variables
For example, you might need to set the following API keys:
```
export OAI_KEY=<your_openai_api_key>
```

### Run the Main Script
In this example, the `ZeroShot` baseline on the `DDXPlus` dataset is executed. Written scripts for running other datasets can be found in `./scripts`.
```
python -m stream_bench.pipelines.run_bench \
    --agent_cfg "configs/agent/zeroshot.yml" \
    --bench_cfg "configs/bench/ddxplus.yml" \
    --entity "photocopier" \
    --use_wandb
```
If you want to run other baselines on the dataset, you can modify `--agent_cfg` to different `<baseline_name>.yml` files, which are located in the `./configs/agent` folder.

## Steps to Implement Your Own Methods
Work in progress
