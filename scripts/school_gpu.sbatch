#!/usr/bin/env bash
# Submit from the repository root, after budget/partition are confirmed.
#SBATCH --job-name=p3-seven-arm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --output=logs/slurm-%j.out
#SBATCH --error=logs/slurm-%j.err
#SBATCH --signal=B:TERM@60

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Submit from the repository root}"
exec bash scripts/run_school_gpu.sh
