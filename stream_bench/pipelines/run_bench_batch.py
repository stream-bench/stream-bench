"""Run non-streaming methods with OpenAI Batch APIs to save costs."""
NON_STREAMING_METHODS = ["zeroshot", "cot", "fewshot"]  # NOTE: add more methods here

import os
import time
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import json
import yaml
import wandb
import jsonlines
from pathlib import Path
from tqdm import tqdm
from openai import OpenAI
from openai.types import Batch
from argparse import ArgumentParser, Namespace

from stream_bench.benchmarks import Bench, load_benchmark
from stream_bench.agents import Agent, load_agent
from stream_bench.llms.oai_chat import OpenAIChat
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

def get_prompt(agent: Agent, bench: Bench, row: dict) -> str:
    x = bench.get_input(row)
    prompt_name = f"prompt_{agent.config['agent_name']}"
    if agent.config.get("mode", False):
        prompt_name += f"_{agent.config['mode']}"
    return x[prompt_name]

def prepare_batch_file(
    agent: Agent,
    bench: Bench,
    save_dir: Path = Path("./batch_upload_files")
) -> Path:
    """Prepare and save the file for uploading to OpenAI Batch API.
    
    Returns:
        Path: The path to the saved file.
    """
    # File preparation
    save_dir = save_dir / bench.__class__.__name__
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{agent.get_name()}_batch.jsonl"
    # Save batch inputs to the file
    if not os.path.exists(save_path):
        print(f"Saving the batch file to {save_path}")
        # Check for existence of response_format
        response_format = agent.config.get("response_format", None)
        with open(save_path, 'w') as f:
            for time_step, row in enumerate(tqdm(bench.get_dataset(), dynamic_ncols=True)):
                custom_id = f"step-{time_step}"
                prompt = get_prompt(agent, bench, row)
                msg = {
                    "custom_id": custom_id,
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": agent.config["llm"]["model_name"],
                        "messages": [
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": agent.config["llm"]["temperature"],
                        "max_tokens": agent.config["llm"]["max_tokens"],
                        "logprobs": True,
                        "top_logprobs": OpenAIChat.TOP_LOGPROBS,
                    }
                }
                if response_format is not None:
                    msg["body"]["response_format"] = response_format
                f.write(json.dumps(msg) + "\n")
    # Check file size
    MAX_FILE_SIZE_MB = 100
    file_size_mb = save_path.stat().st_size / (1024 * 1024)
    print(f"Batch input file size: {file_size_mb:.2f} MB")
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ValueError("File size exceeds the limit of 100 MB. Please split the file.")
    return save_path

def upload_batch_file(filepath: Path) -> Batch:
    """Upload the batch file to OpenAI Batch API.
    
    Returns:
        Batch: The batch object.
    """
    # TODO: check if the file already exists
    client = OpenAI(api_key=os.getenv("OAI_KEY"))
    batch_input_file = client.files.create(
        file=open(filepath, "rb"),
        purpose="batch"
    )
    batch_obj = client.batches.create(
        input_file_id=batch_input_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={
            "filename": filepath.stem
        }
    )
    return batch_obj

def wait_until_finished(
    batch_obj: Batch,
    save_path: Path,
    period: int = 10
) -> Path:
    """Wait until the batch is finished and download the results.
    
    Returns:
        Path: The path to the downloaded file.
    """
    from colorama import Fore, Style
    # Wait until the batch is finished
    client = OpenAI(api_key=os.getenv("OAI_KEY"))
    start_time = time.time()
    while True:
        batch_obj = client.batches.retrieve(batch_obj.id)
        os.system("clear")
        time_elapsed = (time.time() - start_time) / 60
        if batch_obj.status == "completed":
            print(Fore.GREEN + f"Batch completed! (Total time = {time_elapsed:.2f} minutes)" + Style.RESET_ALL)
            break
        print(Fore.YELLOW + f"Batch status: {batch_obj.status} (Time elapsed = {time_elapsed:.2f} minutes)" + Style.RESET_ALL)
        time.sleep(period)
    # Download and save the results
    print(f"Downloading the batch results to {save_path}...")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    batch_results = client.files.content(file_id=batch_obj.output_file_id)
    batch_results.write_to_file(save_path)
    return save_path

def get_step_to_info(batch_download_path: Path) -> dict[int, dict]:
    """Parse the downloaded batch file to get the step-to-info mapping.
    
    Returns:
        dict[int, dict]: The step-to-info mapping of the following format:
        {
            time_step: {
                "output_pred": str,
                "logprobs_pred": list,
                "num_inference_call": 1,
                "num_input_tokens": int,
                "num_output_tokens": int
            }
        }
    """
    step2info = dict()
    with jsonlines.open(batch_download_path) as reader:
        for line in reader:
            custom_id = line["custom_id"]
            time_step = int(custom_id.split("-")[-1])
            choice = line["response"]["body"]["choices"][0]
            log_prob_seq = choice["logprobs"]["content"]
            step2info[time_step] = {
                "output_pred": choice["message"]["content"],
                "logprobs_pred": [[{"token": pos_info["token"], "logprob": pos_info["logprob"]} for pos_info in position["top_logprobs"]] for position in log_prob_seq],
                "num_inference_call": 1,
                "num_input_tokens": line["response"]["body"]["usage"]["prompt_tokens"],
                "num_output_tokens": line["response"]["body"]["usage"]["completion_tokens"]
            }
    return step2info

def main():
    args = setup_args()
    agent_cfg = yaml.safe_load(args.agent_cfg.read_text())
    if agent_cfg["agent_name"] not in NON_STREAMING_METHODS:
        raise ValueError(f"Only non-streaming methods are supported for the Batch API mode. Please choose one from {NON_STREAMING_METHODS}")
    assert agent_cfg["llm"]["series"] == "openai"
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

    # Prepare, upload, wait for, and download from Batch APIs
    BATCH_UPLOAD_DIR = Path("./batch_upload_files")
    BATCH_DOWNLOAD_DIR = Path("./batch_download_files")
    batch_download_path = BATCH_DOWNLOAD_DIR / bench.__class__.__name__ / f"{agent.get_name()}_batch.jsonl"
    if not os.path.exists(batch_download_path):
        file_to_upload = prepare_batch_file(agent, bench, save_dir=BATCH_UPLOAD_DIR)
        batch_obj = upload_batch_file(file_to_upload)
        wait_until_finished(
            batch_obj,
            save_path=batch_download_path
        )
    step2info = get_step_to_info(batch_download_path)

    if args.use_wandb:
        wandb.init(
            project=args.project if (args.project is not None) else f"streambench-{bench_cfg['bench_name']}",
            entity=args.entity,
            name=args.name if (args.name is not None) else agent.get_name(),
            config=merge_dicts(dicts=[agent_cfg, bench_cfg])  # NOTE: agent configurations and benchmark configurations
        )

    for time_step, row in enumerate(tqdm(bench.get_dataset(), dynamic_ncols=True)):
        row['time_step'] = time_step
        model_output = step2info[time_step]["output_pred"]
        prediction = bench.postprocess_generation(model_output, time_step)
        label = bench.get_output(row)
        pred_res = bench.process_results(
            prediction,
            label,
            return_details=True,
            time_step=time_step
        )

        agent.update_log_info(log_data=step2info[time_step])
        if args.use_wandb:
            log_data = merge_dicts(dicts=[agent.get_wandb_log_info(), pred_res])
            wandb.log(data=log_data)
        # NOTE: agent.log() should be called after wandb
        if isinstance(label, int):
            label = bench.LABEL2TEXT[label]
        elif isinstance(label, dict):
            label = label.get("label", json.dumps(label))

        agent.log(label_text=label)

    metrics = bench.get_metrics()
    print(metrics)
    if args.use_wandb:
        wandb.log(data={'final/'+k: v for k, v in metrics.items()})

if __name__ == "__main__":
    main()
