#!/usr/bin/env bash
# Submit with jsub; never run on the login node or set JH_JOBID manually.
set -euo pipefail
: "${JH_JOBID:?Submit this script through the school Phase I jsub scheduler}"
source /hpc/jhinno/modules-4.2/init/bash
module load gcc-12.1.0 cuda-12.8
export P3_SERVER="${P3_SERVER:-$HOME/p3-work/llama.cpp-b12244/build-cuda/bin/llama-server}"
export P3_RUN_ID="${P3_RUN_ID:-school-${P3_MODE:-screening}-$JH_JOBID}"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/run_school_gpu.sh"
