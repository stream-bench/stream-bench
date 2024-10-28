import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import json
import yaml
import wandb
from pathlib import Path
from tqdm import tqdm
from argparse import ArgumentParser, Namespace

from stream_bench.benchmarks import Bench, load_benchmark
from stream_bench.agents import load_agent
from .utils import merge_dicts

def setup_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument(
        "--agent_cfg",
        type=Path,
        required=True,
        help="Path to the agent's config yaml file"
    )
    parser.add_argument(
        "--bench_cfg",
        type=Path,
        required=True,
        help="Path to the benchmark's config yaml file."
    )
    parser.add_argument(
        "--use_wandb",
        action="store_true",
        help="Whether to use wandb for experiment tracking."
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Project name for wandb"
    )
    parser.add_argument(
        "--entity",
        type=str,
        default=None,
        help="Team name for wandb"
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="The name of the experiment for wandb."
    )

    return parser.parse_args()


def main():
    args = setup_args()
    agent_cfg = yaml.safe_load(args.agent_cfg.read_text())
    bench_cfg = yaml.safe_load(args.bench_cfg.read_text())
    assert 'bench_name' in bench_cfg
    agent_cfg["bench_name"] = bench_cfg["bench_name"]
    agent_cfg["split"] = bench_cfg["split"]
    if args.name is not None:
        agent_cfg['exp_name'] = args.name
    print('init agent')
    agent = load_agent(agent_cfg['agent_name'])(agent_cfg)
    bench_cfg['agent'] = agent
    # bench_cfg['agent_callback'] = agent.retrieve_experience
    print('init bench environment')
    bench: Bench = load_benchmark(bench_cfg['bench_name'])(**bench_cfg)
    agent.bench = bench

    if args.use_wandb:
        wandb.init(
            project=args.project if (args.project is not None) else f"streambench-{bench_cfg['bench_name']}",
            entity=args.entity,
            name=args.name if (args.name is not None) else agent.get_name(),
            config=merge_dicts(dicts=[agent_cfg, bench_cfg])  # NOTE: agent configurations and benchmark configurations
        )

    pbar = tqdm(bench.get_dataset(), dynamic_ncols=True, desc="Streaming Progress")
    for time_step, row in enumerate(pbar):
        try:
            row['time_step'] = time_step
            x = bench.get_input(row)  # remove ground truth related information
            x['time_step'] = time_step
            model_output = agent(**x)
            prediction = bench.postprocess_generation(model_output, time_step)
            label = bench.get_output(row)
            pred_res = bench.process_results(
                prediction,
                label,
                return_details=True,
                time_step=time_step
            )

            has_feedback, feedback = bench.give_feedback(model_output, row, pred_res)
            feedback['time_step'] = time_step
            feedback = { **row, **feedback }
            agent.update(has_feedback, **feedback)

            if args.use_wandb:
                log_data = merge_dicts(dicts=[agent.get_wandb_log_info(), pred_res])
                wandb.log(data=log_data)
            # NOTE: agent.log() should be called after wandb
            if isinstance(label, int):
                label = bench.LABEL2TEXT[label]
            elif isinstance(label, dict):
                label = label.get("label", json.dumps(label))

            agent.log(label_text=label)
        except (KeyError, IndexError) as e:
            print(e)
        # Update the description of the progress bar
        pbar.set_postfix(acc=f"{pred_res['rolling_acc'] * 100:.2f}%")

    metrics = bench.get_metrics()
    print(metrics)
    if args.use_wandb:
        wandb.log(data={'final/'+k: v for k, v in metrics.items()})

if __name__ == "__main__":
    main()
