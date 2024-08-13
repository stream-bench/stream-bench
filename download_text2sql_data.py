"""Download text-to-SQL datasets (Spider, CoSQL, and BIRD) and unzip them."""

import os
import gdown
import zipfile
import requests
from tqdm import tqdm
from pathlib import Path
from colorama import Fore, Style

def download_file(url: str, save_path: str) -> None:
    # Stream the download in chunks
    r = requests.get(url, stream=True)
    total_size = int(r.headers.get('content-length', 0))
    chunk_size = 1024  # 1 KB

    with open(save_path, "wb") as f, tqdm(
        desc=save_path,
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                bar.update(len(chunk))

def download_bird(save_dir: str) -> None:
    print(Fore.CYAN + "Downloading and unzipping BIRD..." + Style.RESET_ALL)
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    # Download BIRD
    bird_link = "https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip"
    bird_zip = "bird.zip"
    bird_save_path = f"{save_dir}/{bird_zip}"
    if os.path.exists(bird_save_path):
        print(f"BIRD already exists at {bird_save_path}")
    else:
        print(f"Downloading BIRD to {bird_save_path}")
        download_file(url=bird_link, save_path=bird_save_path)

    # Unzip BIRD
    extract_to_dir = os.path.join(save_dir, "bird")
    if os.path.exists(extract_to_dir):
        print(f"BIRD already unzipped to {extract_to_dir}")

    else:
        with zipfile.ZipFile(bird_save_path, 'r') as zip_ref:
            zip_ref.extractall(save_dir)

        # Search for the file path of "dev_databases.zip" in the folders
        for root, dirs, files in os.walk(save_dir):
            for file in files:
                if file == "dev_databases.zip":
                    db_zip_path = os.path.join(root, file)
                    break

        with zipfile.ZipFile(db_zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to_dir)
        print(f"Unzipped to {extract_to_dir}")

def download_cosql(save_dir: str) -> None:
    print(Fore.CYAN + "Downloading and unzipping CoSQL..." + Style.RESET_ALL)
    # Download CoSQL
    cosql_zip = "cosql.zip"
    cosql_save_path = f"{save_dir}/{cosql_zip}"
    if os.path.exists(cosql_save_path):
        print(f"CoSQL already exists at {cosql_save_path}")
    else:
        print(f"Downloading CoSQL to {cosql_save_path}")
        file_id = "1QQPkUVUN2Leu_ykVchae0FzURZGHPwdJ"
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        gdown.download(url, cosql_save_path, quiet=False)

    # Unzip CoSQL
    extract_to_dir = os.path.join(save_dir, "cosql")
    if os.path.exists(extract_to_dir):
        print(f"CoSQL already unzipped to {extract_to_dir}")
    else:
        with zipfile.ZipFile(cosql_save_path, 'r') as zip_ref:
            zip_ref.extractall(save_dir)
        print(f"Unzipped to {extract_to_dir}")

def download_spider(save_dir: str) -> None:
    print(Fore.CYAN + "Downloading and unzipping Spider..." + Style.RESET_ALL)
    # Download Spider
    spider_zip = "spider.zip"
    spider_save_path = f"{save_dir}/{spider_zip}"
    if os.path.exists(spider_save_path):
        print(f"Spider already exists at {spider_save_path}")
    else:
        print(f"Downloading Spider to {spider_save_path}")
        file_id = "1nkYLYDSGKICePTQnnPl9TgLfdmHI9ctM"
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        gdown.download(url, spider_save_path, quiet=False)

    # Unzip Spider
    extract_to_dir = os.path.join(save_dir, "spider")
    if os.path.exists(extract_to_dir):
        print(f"Spider already unzipped to {extract_to_dir}")
    else:
        with zipfile.ZipFile(spider_save_path, 'r') as zip_ref:
            zip_ref.extractall(save_dir)
        print(f"Unzipped to {extract_to_dir}")

if __name__ == "__main__":
    save_dir = "./data"
    download_bird(save_dir)
    download_cosql(save_dir)
    download_spider(save_dir)
