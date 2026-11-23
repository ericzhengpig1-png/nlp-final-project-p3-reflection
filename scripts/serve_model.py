import argparse
import json
import os
import subprocess
from pathlib import Path

from setup_baseline import ROOT, digest


def main():
    parser = argparse.ArgumentParser(description="Start the pinned model on the allocated GPU node.")
    parser.add_argument("--llama-server", required=True, type=Path)
    parser.add_argument("--device", required=True, help="From llama-server --list-devices")
    parser.add_argument("--weights", type=Path, help="Use a verified GGUF outside models/")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    model = json.loads((ROOT / "configs/baseline.json").read_bytes())["model"]
    weights = (args.weights or ROOT / "models" / model["file"]).resolve()
    binary = str(args.llama_server.resolve())
    build = subprocess.check_output([binary, "--version"], stderr=subprocess.STDOUT, text=True)
    if f'build {model["llama_cpp_build"][1:]},' not in build:
        raise ValueError(f'Expected llama.cpp {model["llama_cpp_build"]}, got {build.strip()}')
    if digest(weights) != model["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {weights}")
    print(build.strip(), flush=True)
    print(f'weights_sha256={model["sha256"]} device={args.device}', flush=True)
    command = [
        binary, "--model", str(weights), "--alias", f'{model["file"]}@{model["revision"]}',
        "--host", "127.0.0.1", "--port", str(args.port), "--device", args.device,
        "--n-gpu-layers", "999", "--fit", "off", "--ctx-size", str(model["context_tokens"]),
        "--parallel", "1", "--no-context-shift", "--no-cache-prompt",
    ]
    if os.name == "posix":
        os.execv(binary, command)
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    main()
