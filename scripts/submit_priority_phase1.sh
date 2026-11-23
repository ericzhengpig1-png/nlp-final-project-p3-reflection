#!/usr/bin/env bash
# Login-node submission only; inference is delegated to allocated GPU jobs.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
: "${P3_CAMPAIGN:?Set a new campaign ID}"
[[ "$P3_CAMPAIGN" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid campaign ID' >&2; exit 2; }
[[ -z "$(git status --porcelain)" ]] || { echo 'Commit changes before submission' >&2; exit 2; }
mkdir "logs/$P3_CAMPAIGN-submission"
record="$ROOT/logs/$P3_CAMPAIGN-submission/jobs.tsv"
git rev-parse HEAD > "logs/$P3_CAMPAIGN-submission/git-commit.txt"
printf 'job_id\tmode\tseed\ttask_index\trun_id\n' > "$record"
previous="${P3_BUILD_JOB:-}"
[[ -z "$previous" || "$previous" =~ ^[0-9]+$ ]] || { echo 'Invalid build job ID' >&2; exit 2; }
submit_gpu() {
    local mode="$1" seed="$2" task="$3" run="$4" response job
    local dependency=()
    if [[ -n "$previous" ]]; then dependency=(-w "done($previous)"); fi
    response="$(jsub -q ai -n 4 -R 'span[hosts=1]' -gpgpu '1 mig=2' -M 16384 -W 10 \
        "${dependency[@]}" -J "p3-$mode" -o "$ROOT/logs/unischeduler-%J.out" \
        -e "$ROOT/logs/unischeduler-%J.err" env P3_MODE="$mode" P3_SEEDS="$seed" \
        P3_TASK_INDEX="$task" P3_CONDITIONS=A,B,S1,S4 P3_RUN_ID="$run" \
        bash "$ROOT/scripts/school_gpu_phase1.sh")"
    printf '%s\n' "$response"
    job="$(sed -n 's/^Job <\([0-9][0-9]*\)>.*/\1/p' <<< "$response")"
    [[ "$job" =~ ^[0-9]+$ ]] || { echo 'Cannot parse submitted job ID; inspect scheduler before retrying' >&2; exit 1; }
    printf '%s\t%s\t%s\t%s\t%s\n' "$job" "$mode" "$seed" "$task" "$run" >> "$record"
    previous="$job"
}
submit_gpu smoke 4051 0 "$P3_CAMPAIGN-smoke"
runs=()
for seed in 4051 4052; do
    for task in {0..9}; do
        run="$P3_CAMPAIGN-s$seed-t$task"
        submit_gpu shard "$seed" "$task" "$run"
        runs+=("$ROOT/logs/$run")
    done
done
response="$(jsub -q normal -n 1 -M 4096 -W 5 -w "done($previous)" -J p3-merge \
    -o "$ROOT/logs/unischeduler-%J.out" -e "$ROOT/logs/unischeduler-%J.err" \
    "$ROOT/.venv/bin/python" "$ROOT/scripts/merge_screening.py" \
    --output "$ROOT/logs/$P3_CAMPAIGN-merged" "${runs[@]}")"
printf '%s\n' "$response"
printf '%s\n' "$response" > "logs/$P3_CAMPAIGN-submission/merge-job.txt"
printf 'Submission records: %s\n' "$record"
