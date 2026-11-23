# 学校 GPU：七组实验部署与运行

更新：2026-11-23。七组入口与学校脚本已接入，验证记录见[就绪检查报告](../reports/seven-arm-readiness.md)。**本次只完成实现、无模型检查和 GitHub 提交；未启动本地模型或学校实验。** 5 GPU 小时仍是前序方案的参考预算，实际分区、account/QoS、余额及获批时限尚需由课程确认。

七组为 A（无反思）、B（原反思）、S1（事实依据）、S2（失败归因）、S3（更新）、S4（剩余目标）、S5（信息密度）。每组同十题、同 4051/4052 两种子，共 140 单元，最多 420 次尝试；使用[冻结协议](../planning/seven-arm-screening.md)。首轮行为不一致会停止并保存证据，不能将其解释成反思收益。

## 1. 选择学校入口

主流程适用于 **HPC 二期 NVIDIA / Slurm**，不表示已经确认课程账号权限。

- [学校登录说明](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/connection/)：SSO 门户 `https://hpc2login.hpc.hkust-gz.edu.cn/`，网页“应用仓库 → Terminal”或 SSH。
- [分区表](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/queue/)：由课程确认可用 GPU 分区、account、QoS；不要猜官网示例账号。
- 容器/Jupyter 见第 9 节；HPC 一期的调度命令不能直接套用本 Slurm 模板。

本地仅管理代码和回收结果。依赖安装、资源下载与 CPU 检查在学校允许的准备环境完成；模型服务与取分仅在获分配的 GPU 节点运行。脚本不申请 GPU，不调用 `sbatch`，普通登录节点直接执行会被拒绝。

## 2. 获取已提交的实现

使用分支 **`feat/seven-arm-school-gpu`**，在 GitHub 记录该分支的完整提交 SHA；学校 clone 后核对同一 SHA。相关文件：

| 文件 | 作用 |
| --- | --- |
| `configs/seven_arm.json` | 固定 A/B/S1–S5、种子、配置与指令 SHA-256 |
| `scripts/run_experiment.py` | 共用动作循环、轮转、首轮核对、配对汇总及失败留档 |
| `scripts/run_school_gpu.sh` | GPU/端口/代码预检、启动服务、等待就绪、退出清理 |
| `scripts/school_gpu.sbatch` | 一节点、一 GPU、串行七组的 Slurm 模板 |
| `scripts/serve_model.py` | 固定版本/权重检查，可指定端口，绑定 127.0.0.1 |

模型、数据、虚拟环境和原始日志不随 Git 上传；在学校下载并校验。`.draft.txt` 是保留的提示词文件名，当前实验内容由 `seven_arm.json` 的哈希冻结。更改文字需明确形成新的协议版本，不能在两种子之间修改。

## 3. 登录学校并克隆相同版本

本地 PowerShell，HPC 二期示例：

```powershell
$HpcUser = Read-Host '学校 SSO 用户名（邮箱前缀）'
ssh "$HpcUser@hpc2login.hpc.hkust-gz.edu.cn"
```

接下来是学校终端里的 **Bash**。用学校分配的持久共享目录；示例放在家目录下，若课程指定项目盘，请替换 `P3_WORK` 的值。

```bash
hostname
uname -m
command -v sbatch
export P3_WORK="$HOME/p3-work"
mkdir -p "$P3_WORK"
cd "$P3_WORK"
git clone --branch feat/seven-arm-school-gpu https://github.com/ericzhengpig1-png/nlp-final-project-p3-reflection.git repo
cd "$P3_WORK/repo"
export P3_REPO="$PWD"
git rev-parse HEAD
git status --short
```

远端 SHA 必须与本地提交的 SHA 相同。准备取分时冻结此版本；作业运行过程中不 `git pull` 或修改配置。需要更新时结束当前版本的运行，再部署新提交。

**学校无法访问 GitHub 时的替代方式：**本地在已提交的仓库内运行 `git bundle create ..\p3-school-gpu.bundle feat/seven-arm-school-gpu`，通过学校门户“我的数据”上传该 bundle；学校在目标目录运行 `git clone --branch feat/seven-arm-school-gpu /实际上传路径/p3-school-gpu.bundle repo`。bundle 保留 Git 提交信息，只包含已提交内容。学校门户支持上传与下载，见[用户家目录说明](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/data/user-data/)。数据和模型若也无法联网下载，可上传原始下载文件，仍按脚本校验哈希。

## 4. 学校机器创建 Linux 环境与下载资源

全部在学校环境执行。参考仓库已验证的 Linux x86_64 / Python 3.10 依赖；若 `uname -m` 不是 `x86_64`，不要使用后面的 x64 二进制包。

安装 uv 的方式来自[官方说明](https://docs.astral.sh/uv/getting-started/installation/)。已有 uv 时跳过前两行。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
cd "$P3_REPO"
uv venv --python 3.10 .venv
uv pip sync --python .venv/bin/python requirements-baseline.txt
uv pip check --python .venv/bin/python
.venv/bin/python --version
.venv/bin/python scripts/setup_baseline.py --model
```

下载脚本会获取并校验十题开发数据、固定版本 Reflexion 原文件与 GGUF 权重。它不会启动推理；当前也不会准备三十题留出集。不能遇到安装报错就随意放松依赖版本，否则七组环境不再可追溯；需要编译器时使用学校提供的软件模块或兼容 Linux 镜像。

学校 CPU 环境中执行无模型检查：

```bash
.venv/bin/python scripts/run_experiment.py --check-only
.venv/bin/python -m unittest discover -s tests -v
bash -n scripts/run_school_gpu.sh scripts/school_gpu.sbatch
```

`--check-only` 预期显示 `check: passed`、7 组、10 题、2 种子、140 单元及 `model_requests: 0`。它校验版本、固定配置/提示词/上游文件与任务文件，不连接模型服务、不加载权重。测试使用固定回复、真实 CPU 文本环境和临时模拟进程，不产生实验成绩。

## 5. 学校准备固定版本 llama.cpp

本项目固定为 **b12244**。下面是 [b12244 官方发布页](https://github.com/ggml-org/llama.cpp/releases/tag/b12244)当前提供的 Linux x64 CUDA 12.8 二进制与配套库路径；要求服务器驱动和系统运行库兼容。不要下载 Windows Vulkan 包，也不要因为部署方便更换模型或后端版本。

在学校准备环境下载并解压到仓库外，避免产生未追踪的运行文件：

```bash
export P3_RUNTIME="$P3_WORK/llama-b12244-cuda12"
mkdir -p "$P3_RUNTIME"
cd "$P3_RUNTIME"
curl -fL --retry 3 -o llama.tar.gz https://github.com/ggml-org/llama.cpp/releases/download/b12244/llama-b12244-bin-ubuntu-cuda-12.8-x64.tar.gz
curl -fL --retry 3 -o cudart.tar.gz https://github.com/ggml-org/llama.cpp/releases/download/b12244/cudart-llama-b12244-bin-ubuntu-cuda-12.8-x64.tar.gz
```

下列 SHA-256 于 2026-11-23 从 GitHub 发布资源元数据核对：

```bash
sha256sum -c <<'CHECKSUMS'
8ec620602bf8b0a7b8fe222cf46df73c38e9cf26ab1ea265d13180addca68ac0  llama.tar.gz
09f39d31e004d3f66c837e1368b81b0ed2ac0e8713a69bf96346a4be5691d099  cudart.tar.gz
CHECKSUMS
tar -xzf llama.tar.gz
tar -xzf cudart.tar.gz
export P3_SERVER="$(find "$P3_RUNTIME" -type f -name llama-server -print -quit)"
P3_LIBS="$(find "$P3_RUNTIME" -type f -name '*.so*' -printf '%h\n' | sort -u | paste -sd: -)"
export LD_LIBRARY_PATH="${P3_LIBS}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
test -n "$P3_SERVER"
"$P3_SERVER" --version
```

预期版本含 build 12244。若出现 GLIBC/GLIBCXX、CUDA 库或驱动兼容报错，先在学校选择兼容的容器/运行环境，或在匹配节点上编译**同一固定 tag**并保持版本可核验；不要直接升级后端继续取分。当前尚未获得学校 OS/驱动信息，因此不能保证这个预编译包在你的节点上直接加载。

以上 `export` 在当前登录会话生效；重连后提交作业前，应重新设置 `P3_WORK`、`P3_REPO`、`P3_RUNTIME`、`P3_SERVER` 和库路径。批作业通过 `--export=ALL` 继承它们。

## 6. 将来获批后提交 Slurm 作业

**以下 `sbatch` 会实际申请 GPU 并启动实验，现在先准备到第 5 节即可。** 在学校登录节点执行；从仓库根目录提交，Slurm 批脚本复制到内部目录后仍通过 `SLURM_SUBMIT_DIR` 找到项目。

```bash
cd "$P3_REPO"
mkdir -p logs
sinfo -o '%P %G %l %a'
read -r -p '课程允许的 NVIDIA GPU 分区: ' P3_PARTITION
read -r -p '本次已批准的作业时限 HH:MM:SS: ' P3_TIME
export P3_RUN_ID="school-seven-$(date +%Y%m%d-%H%M%S)"
export P3_SEEDS='4051 4052'
# P3_SERVER 和 LD_LIBRARY_PATH 沿用第 5 节；默认 Python 为仓库 .venv/bin/python。
# 可选：export P3_PORT=23901；省略时从 20000–39999 选端口并检查是否空闲。
# 可选：export P3_WEIGHTS=/学校共享目录/固定模型.gguf
sbatch --partition="$P3_PARTITION" --time="$P3_TIME" --export=ALL scripts/school_gpu.sbatch
```

课程若要求计费账号或 QoS，在 `sbatch` 增加实际的 `--account=...` / `--qos=...`。不在脚本写死分区和时限，也不将参考预算视为已获批。默认资源为 1 GPU、4 CPU、16G 内存；设备必须有 CUDA0，不回退 CPU。模型服务与实验在同一分配节点内，通过本机回环端口通信，不需要连接本地模型。[学校作业说明](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/job2/)

两种子默认同一作业内完成，更便于保持硬件一致。如果预算按轮批准，可先 `export P3_SEEDS='4051'`，下一轮用新 run ID 和 `P3_SEEDS='4052'`，各 70 单元；4052 单独运行仍保留预定的一位轮转偏移。分轮时要求同一冻结提交、同型号设备和后端配置，两份 manifest 均保留。单种子摘要只代表单轮，不伪称两轮完成；查看两份报告后才比较候选稳定性。

脚本会依次核对 GPU 分配、干净 Git 工作区、资源/指令、空闲端口、CUDA 设备、固定后端/权重及 `/health`。Slurm 下要求调度器提供有效的 `CUDA_VISIBLE_DEVICES`，不会仅因看得到物理 GPU 就在 CPU 作业中启动模型；该变量的分配语义见 [Slurm GPU 管理说明](https://slurm.schedmd.com/gres.html#GPU_Management)。所有生成请求串行发到同一个服务 slot。

正常结束、失败或可捕获的 INT/TERM 都会清理自己启动的服务和实验进程组；超过就绪时限会报错，完整服务日志仍保留。批模板通过 `B:TERM@60` 在时限前通知包装脚本清理；该通知可能提前额外 60 秒，实际可用实验时间应留出余量。[Slurm 信号说明](https://slurm.schedmd.com/sbatch.html#OPT_signal) SIGKILL、节点故障等无法执行 Python 清理，必须结合调度器状态和已刷盘的 JSONL 判断完成情况。

## 7. 查看进度与验收产物

学校登录节点，使用 `sbatch` 返回的作业号：

```bash
read -r -p '作业号: ' P3_JOB_ID
squeue -u "$USER"
scontrol show job "$P3_JOB_ID"
tail -f "logs/$P3_RUN_ID-job/experiment.log"
```

`tail -f` 的 Ctrl+C 只结束查看。真正取消作业执行 `scancel "$P3_JOB_ID"`；模型服务结束后批作业应退出。结束后查询状态和实际分配时长：

```bash
sacct -j "$P3_JOB_ID" --format=JobID,JobName,State,ExitCode,Elapsed,AllocTRES
```

`sbatch` 返回作业号表示提交成功；实验是否完成看摘要和调度状态。Slurm 不搬运仓库和模型，计算节点必须能读到同一共享目录。[Slurm 官方说明](https://slurm.schedmd.com/sbatch.html)

| 产物 | 核对内容 |
| --- | --- |
| `logs/<run-id>/manifest.json` | Git 提交、全部指令、配置/源文件/任务哈希、实际顺序、环境版本、节点与作业号 |
| `logs/<run-id>/trace.jsonl` | 完整请求、响应、动作/观察、反思、重置记忆、首轮一致性及错误 |
| `logs/<run-id>/task_results.jsonl` | 每完成一个任务×组×种子立即追加；断点证据，不自动续跑/覆盖 |
| `logs/<run-id>/summary.json` | 状态、完成单元数、逐种子成功/恢复、相对 A/B 胜负、成本及跨种子平均 |
| `logs/<run-id>-job/` | `gpu.csv`、设备、预检、模型服务/实验日志及 `job.json` 包装脚本时长/退出码 |
| `logs/slurm-<job-id>.out/.err` | 调度器捕获的输出与错误 |

完整两轮要求 `status=complete`、`completed_units=expected_units=140`、`full_two_seed_screening=true`；每种子每组 10 题，首轮核对全部通过。分轮运行各 70 单元，`full_two_seed_screening=false` 是预期值。恢复率按首败分母，零分母输出 null；不完整运行只按已完成任务报告，并禁止给出完整排名。

`first_attempt_audit.matched=false`、`run_error` 或 `status=failed/interrupted/running` 要先排查，不能算作任务失败。首轮不一致可能来自输入、种子或 CUDA 后端非确定性；保留证据、确定原因后再决定是否需要新协议。模型输出到 256 token 上限仍按既有规则记录，未自动提高预算。

模型成本分开记录请求数、输入/输出 token、后端推理时间与环境动作；失败请求计入请求数，没有返回的 token/时间不可估造。组内成本是已完成单元成本，`all_cost_including_incomplete` 额外包含中断单元已知成本。实际计费卡时按调度器分配时长 × GPU 数统计，不能拿纯推理秒数代替。

## 8. 回收结果

先将调度记录存入本次作业目录，再打包完整证据：

```bash
cd "$P3_REPO"
sacct -j "$P3_JOB_ID" --format=JobID,JobName,State,ExitCode,Elapsed,AllocTRES > "logs/$P3_RUN_ID-job/sacct.txt"
tar -czf "$P3_WORK/$P3_RUN_ID.tar.gz" \
  "logs/$P3_RUN_ID" "logs/$P3_RUN_ID-job" \
  "logs/slurm-$P3_JOB_ID.out" "logs/slurm-$P3_JOB_ID.err" \
  configs prompts/reflection_candidates
sha256sum "$P3_WORK/$P3_RUN_ID.tar.gz"
```

如果在预检或加载模型时就失败，可能尚未创建实验目录；此时按实际存在的目录打包作业日志。用门户“我的数据”下载，或本地 PowerShell 用 `scp 用户名@hpc2login.hpc.hkust-gz.edu.cn:/实际路径/结果.tar.gz .` 下载。保留失败日志及原始提交 SHA，不为补齐结果覆盖旧运行目录。当前不自动恢复中断运行；先确认影响范围和剩余预算，再以新 run ID 决定重跑范围。

## 9. 课程 GPU 容器 / Jupyter 路线

学校另有 [AI 容器平台](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/k8s/feature-preview/)。在课程提供的**远端、已分配 GPU 的容器**中完成第 3–5 节，持久化工作目录。获批启动后，在容器 Terminal 使用同一包装脚本：

```bash
cd "$P3_REPO"
export P3_CONTAINER=1
export P3_RUN_ID="school-container-$(date +%Y%m%d-%H%M%S)"
export P3_SEEDS='4051 4052'
bash scripts/run_school_gpu.sh
```

`P3_CONTAINER=1` 是对已有学校 GPU 分配的显式声明，不要在本地或普通登录节点设置它。该方式不执行 `sbatch`，需用平台的时限/预算控制及持久任务机制；浏览器关闭后进程是否存活取决于平台。脚本退出会清理模型服务，但容器占用的 GPU 需在平台停止/释放，不能靠关闭 Notebook 标签页释放资源。

学校实际节点的驱动兼容性、课程分区/account 权限、下载可达性和真实推理吞吐尚未远端验收。现在已具备可部署的入口与无模型检查证据，真实成绩和卡时要等用户批准后的学校作业产生。
