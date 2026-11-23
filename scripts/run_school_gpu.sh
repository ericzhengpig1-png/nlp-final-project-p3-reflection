#!/usr/bin/env bash
# Run only in an allocated school GPU job/container. Does not submit a job.
set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" && -z "${JH_JOBID:-}" && "${P3_CONTAINER:-0}" != 1 ]]; then
    echo 'Refusing to start: use a school Slurm/UniScheduler allocation, or P3_CONTAINER=1 inside an allocated school GPU container.' >&2
    exit 2
fi
if [[ ( -n "${SLURM_JOB_ID:-}" || -n "${JH_JOBID:-}" ) && ( -z "${CUDA_VISIBLE_DEVICES:-}" || "${CUDA_VISIBLE_DEVICES}" == -1 || "${CUDA_VISIBLE_DEVICES}" == NoDevFiles ) ]]; then
    echo 'Scheduler has not exposed an allocated GPU through CUDA_VISIBLE_DEVICES; refusing to start.' >&2
    exit 2
fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
P3_PYTHON="${P3_PYTHON:-$ROOT/.venv/bin/python}"
: "${P3_SERVER:?Set P3_SERVER to the pinned Linux llama-server executable}"
: "${P3_RUN_ID:?Set a new P3_RUN_ID}"
[[ "$P3_RUN_ID" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Invalid P3_RUN_ID' >&2; exit 2; }
[[ -x "$P3_PYTHON" && -x "$P3_SERVER" ]] || { echo 'Missing Python or llama-server executable' >&2; exit 2; }
command -v git >/dev/null || { echo 'Git is required for source verification' >&2; exit 2; }
git_status="$(git status --porcelain)"
[[ -z "$git_status" ]] || { echo 'Commit all repository changes before running' >&2; exit 2; }
[[ ! -e "logs/$P3_RUN_ID" ]] || { echo 'Run ID already exists; refusing to overwrite' >&2; exit 2; }
P3_PORT="${P3_PORT:-$((20000 + RANDOM % 20000))}"
P3_READY_TIMEOUT="${P3_READY_TIMEOUT:-180}"
[[ "$P3_READY_TIMEOUT" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid P3_READY_TIMEOUT' >&2; exit 2; }
mode_args=()
case "${P3_MODE:-screening}" in
    screening) read -r -a seeds <<< "${P3_SEEDS:-4051 4052}" ;;
    smoke) mode_args=(--smoke); seeds=(4051) ;;
    shard)
        if [[ "${P3_EXPERIMENT:-}" == supplementary-4053 ]]; then
            [[ "${P3_TASK_INDEX:-}" =~ ^([0-9]|1[0-9])$ && "${P3_SEEDS:-}" == 4053 ]] || { echo 'Supplementary shard requires task 0..19 and seed 4053' >&2; exit 2; }
        else
            [[ "${P3_TASK_INDEX:-}" =~ ^[0-9]$ && "${P3_SEEDS:-}" =~ ^405[12]$ ]] || { echo 'Shard requires P3_TASK_INDEX=0..9 and one P3_SEEDS=4051 or 4052' >&2; exit 2; }
        fi
        mode_args=(--task-index "$P3_TASK_INDEX"); seeds=("$P3_SEEDS") ;;
    *) echo 'P3_MODE must be smoke, shard or screening' >&2; exit 2 ;;
esac
condition_text="${P3_CONDITIONS:-A B S1 S2 S3 S4 S5}"
read -r -a conditions <<< "${condition_text//,/ }"
mode_args+=(--conditions "${conditions[@]}")
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"
export PYTHONUNBUFFERED=1
export P3_JOB_LOG_DIR="$ROOT/logs/$P3_RUN_ID-job"
mkdir "$P3_JOB_LOG_DIR"
server_pid=''
runner_pid=''
started="$(date +%s)"

stop_group() {
    local pid="$1"
    [[ -n "$pid" ]] || return 0
    kill -TERM -- "-$pid" 2>/dev/null || true
    for _ in {1..20}; do
        kill -0 -- "-$pid" 2>/dev/null || break
        sleep 0.2
    done
    kill -KILL -- "-$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}
cleanup() {
    local result=$?
    trap - EXIT INT TERM
    stop_group "$runner_pid"
    stop_group "$server_pid"
    local ended
    ended="$(date +%s)"
    "$P3_PYTHON" - "$P3_JOB_LOG_DIR/job.json" "$started" "$ended" "$result" "$P3_PORT" <<'PY'
import json, os, socket, sys
from pathlib import Path
path, start, end, code, port = sys.argv[1:]
Path(path).write_text(json.dumps({
    "hostname": socket.gethostname(), "slurm_job_id": os.getenv("SLURM_JOB_ID"),
    "unischeduler_job_id": os.getenv("JH_JOBID"),
    "unischeduler_gpu_allocation": os.getenv("JH_GPU_RANK"),
    "scheduler": "unischeduler" if os.getenv("JH_JOBID") else ("slurm" if os.getenv("SLURM_JOB_ID") else "container"),
    "cuda_visible_devices": os.getenv("CUDA_VISIBLE_DEVICES"),
    "started_epoch": int(start), "ended_epoch": int(end), "wrapper_seconds": int(end)-int(start),
    "exit_code": int(code), "port": int(port),
    "note": "Use scheduler accounting for billed GPU allocation time, including preparation and cleanup."
}, indent=2) + "\n", encoding="utf-8")
PY
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

command -v setsid >/dev/null
nvidia-smi --query-gpu=name,uuid,driver_version,memory.total --format=csv > "$P3_JOB_LOG_DIR/gpu.csv"
export P3_RUNTIME_SHA256="$("$P3_PYTHON" - "$P3_SERVER" <<'PY'
import hashlib, sys
from pathlib import Path
binary = Path(sys.argv[1]).resolve()
parts = [(p.name, hashlib.sha256(p.read_bytes()).hexdigest())
         for p in sorted({binary, *binary.parent.glob('lib*.so*')}) if p.is_file()]
print(hashlib.sha256(repr(parts).encode()).hexdigest())
PY
)"
export P3_GPU_TYPE_DRIVER="$("$P3_PYTHON" - "$P3_JOB_LOG_DIR/gpu.csv" <<'PY'
import csv, json, sys
with open(sys.argv[1]) as source:
    rows = list(csv.reader(source))[1:]
print(json.dumps(sorted({(r[0].strip(), r[2].strip()) for r in rows})))
PY
)"
"$P3_PYTHON" scripts/run_experiment.py --check-only --seeds "${seeds[@]}" "${mode_args[@]}" > "$P3_JOB_LOG_DIR/preflight.json"
"$P3_PYTHON" - "$P3_PORT" <<'PY'
import socket, sys
port = int(sys.argv[1])
if not 1024 <= port <= 65535:
    raise SystemExit("P3_PORT must be between 1024 and 65535")
with socket.socket() as sock:
    sock.bind(("127.0.0.1", port))
PY
"$P3_SERVER" --list-devices > "$P3_JOB_LOG_DIR/devices.txt" 2>&1
grep -Eq 'CUDA0[[:space:]:]' "$P3_JOB_LOG_DIR/devices.txt" || { echo 'CUDA0 unavailable; refusing CPU fallback' >&2; exit 2; }
weights=()
if [[ -n "${P3_WEIGHTS:-}" ]]; then weights=(--weights "$P3_WEIGHTS"); fi
setsid "$P3_PYTHON" scripts/serve_model.py --llama-server "$P3_SERVER" --device CUDA0 \
    --port "$P3_PORT" "${weights[@]}" > "$P3_JOB_LOG_DIR/server.log" 2>&1 &
server_pid=$!
ready=0
deadline=$((SECONDS + P3_READY_TIMEOUT))
while (( SECONDS < deadline )); do
    kill -0 "$server_pid" 2>/dev/null || { echo 'Model server exited during startup; see server.log' >&2; exit 1; }
    if "$P3_PYTHON" - "$P3_PORT" <<'PY'
import json, sys
from urllib.request import urlopen
try:
    with urlopen(f"http://127.0.0.1:{int(sys.argv[1])}/health", timeout=2) as response:
        healthy = json.load(response).get("status") == "ok"
except Exception:
    healthy = False
sys.exit(0 if healthy else 1)
PY
    then ready=1; break; fi
    sleep 1
done
[[ "$ready" == 1 ]] || { echo 'Timed out waiting for model server' >&2; exit 1; }
kill -0 "$server_pid" 2>/dev/null || { echo 'Model server exited before experiment' >&2; exit 1; }
setsid "$P3_PYTHON" scripts/run_experiment.py --run-id "$P3_RUN_ID" --seeds "${seeds[@]}" \
    "${mode_args[@]}" --server "http://127.0.0.1:$P3_PORT" > "$P3_JOB_LOG_DIR/experiment.log" 2>&1 &
runner_pid=$!
wait "$runner_pid"
