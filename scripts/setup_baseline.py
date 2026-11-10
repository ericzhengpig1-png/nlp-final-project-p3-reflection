import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(2**20), b""):
            sha.update(chunk)
    return sha.hexdigest()


def fetch(url, destination, expected):
    if destination.is_file() and digest(destination) == expected:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {destination.name}", flush=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as directory:
        temporary = Path(directory) / destination.name
        with urlopen(url, timeout=90) as response, temporary.open("wb") as file:
            shutil.copyfileobj(response, file)
        if digest(temporary) != expected:
            raise ValueError(f"SHA-256 mismatch: {url}")
        temporary.replace(destination)


def main():
    parser = argparse.ArgumentParser(description="Fetch and verify the pinned P3 assets.")
    parser.add_argument("--archive", type=Path, help="Use an existing ALFWorld archive")
    parser.add_argument("--model", action="store_true", help="Also fetch the GGUF weights")
    args = parser.parse_args()
    config = json.loads((ROOT / "configs/baseline.json").read_bytes())
    registry = json.loads((ROOT / "configs/task_registry.json").read_bytes())
    dataset = config["dataset"]
    archive = args.archive
    if archive is None:
        archive = ROOT / "data" / dataset["url"].rsplit("/", 1)[-1]
        fetch(dataset["url"], archive, dataset["sha256"])
    elif digest(archive) != dataset["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {archive}")
    with ZipFile(archive) as zip_file:
        for task in registry["development"]:
            member = f"{task}/game.tw-pddl"
            path = ROOT / "data/alfworld" / member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(zip_file.read(member))
    reflexion = config["reflexion"]
    base = f'https://raw.githubusercontent.com/noahshinn/reflexion/{reflexion["commit"]}/alfworld_runs'
    for name, expected in reflexion["files"].items():
        fetch(f"{base}/{name}", ROOT / "data/reflexion" / name, expected)
    if args.model:
        model = config["model"]
        hub = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
        url = f'{hub}/{model["id"]}/resolve/{model["revision"]}/{model["file"]}'
        fetch(url, ROOT / "models" / model["file"], model["sha256"])
    print(f'Assets ready for {len(registry["development"])} development tasks.')


if __name__ == "__main__":
    main()
