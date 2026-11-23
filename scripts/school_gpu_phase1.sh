#!/usr/bin/env bash
# Submit with jsub; never run on the login node or set JH_JOBID manually.
set -euo pipefail
: "${JH_JOBID:?Submit this script through the school Phase I jsub scheduler}"
source /hpc/jhinno/modules-4.2/init/bash
module load gcc-12.1.0 cuda-12.8
export PATH="$HOME/p3-work/runtime-tools/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/p3-work/runtime-tools/lib:${LD_LIBRARY_PATH:-}"
export P3_SERVER="${P3_SERVER:-$HOME/p3-work/llama.cpp-b12244/build-cuda-gcc12/bin/llama-server}"
export P3_RUN_ID="${P3_RUN_ID:-school-${P3_MODE:-screening}-$JH_JOBID}"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
CUDA_VISIBLE_DEVICES="$("${P3_PYTHON:-$ROOT/.venv/bin/python}" "$ROOT/scripts/school_gpu_device.py")"
export CUDA_VISIBLE_DEVICES
exec bash "$ROOT/scripts/run_school_gpu.sh"
