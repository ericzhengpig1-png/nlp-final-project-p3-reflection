# 学校 HPC 一期：冒烟与后台七组实验

2026-11-23 用户已授权在学校先冒烟、通过后运行七组。当前账号使用 `hpc1login.hpc.hkust-gz.edu.cn` 的 UniScheduler；使用 `jsub`，不是二期的 `sbatch`。排队和运行以 `jjobs` 的实际状态为准。

## 固定输入与规模

- 复用 `configs/seven_arm.json` 的 A/B/S1–S5、提示词、模型、采样和重试预算。
- 冒烟：`P3_MODE=smoke`，registry 第一题、seed 4051、七组，共 7 单元，1 GPU、最多 15 分钟。单题成功率不能用来筛选方案。
- 正式筛选：`P3_MODE=screening`，10 题、4051/4052 两种子、七组，共 140 单元，1 GPU、最多 300 分钟。与冒烟分目录，不合并指标。
- 结果都写入学校共享盘的 `logs/`；断开 SSH 不会取消已提交的批作业。模型推理只发生在调度器分配的 GPU 节点。

## 已准备的 CUDA 运行库

源代码为 llama.cpp `b12244`，commit `d5bbcd1f31dba754f716a26c3a4784502a6b9ede`。源码通过 `git archive HEAD` 生成 LF tar，SHA-256：`96bccbdea51ea9774292e1b90b5a7c5945985f6bc4a02c91f23801b8508fb1ea`。学校路径为 `$HOME/p3-work/llama.cpp-b12244`，编译在 normal 队列的 CPU 作业执行。

```bash
source /hpc/jhinno/modules-4.2/init/bash
module load gcc-12.1.0 cuda-12.8 cmake-3.24
cd "$HOME/p3-work/llama.cpp-b12244"
cmake -S . -B build-cuda -DCMAKE_BUILD_TYPE=Release \
  -DGGML_CUDA=ON -DGGML_NATIVE=OFF -DCMAKE_CUDA_ARCHITECTURES=80 \
  -DLLAMA_BUILD_NUMBER=12244 -DLLAMA_BUILD_COMMIT=d5bbcd1f \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
  -DLLAMA_OPENSSL=OFF
cmake --build build-cuda --target llama-server --parallel 8
```

归档没有 `.git`，所以显式设置与实际源代码一致的 build number/commit；模型权重与运行时版本检查保持启用。构建参数参考[固定版本的官方构建说明](https://github.com/ggml-org/llama.cpp/blob/b12244/docs/build.md)。入口 `scripts/school_gpu_phase1.sh` 加载相同 GCC/CUDA 模块，并默认使用上述 `build-cuda/bin/llama-server`。

## 提交与成功依赖

以下命令在学校仓库根目录执行。先同步并确认干净提交；从提交冒烟到正式作业结束，保持此目录的代码、运行库和冻结输入不变。编译完成并通过预检后再提交；若编译仍在排队/运行，可给冒烟增加 `-w 'done(实际编译作业号)'`。

```bash
cd "$HOME/p3-work/repo"
git status --porcelain
.venv/bin/python scripts/run_experiment.py --check-only --smoke
.venv/bin/python scripts/run_experiment.py --check-only
mkdir -p logs
jsub -q gpu -n 4 -R 'span[hosts=1]' -gpgpu 1 -M 16384 -W 15 \
  -J p3-smoke -o "$PWD/logs/unischeduler-%J.out" -e "$PWD/logs/unischeduler-%J.err" \
  env P3_MODE=smoke bash "$PWD/scripts/school_gpu_phase1.sh"
```

记下返回的冒烟作业号，再提交正式任务的成功依赖。`SMOKE_JOB` 必须替换成刚返回的实际数字：

```bash
SMOKE_JOB=实际冒烟作业号
jsub -q gpu -n 4 -R 'span[hosts=1]' -gpgpu 1 -M 16384 -W 300 \
  -w "done($SMOKE_JOB)" -J p3-screening \
  -o "$PWD/logs/unischeduler-%J.out" -e "$PWD/logs/unischeduler-%J.err" \
  env P3_MODE=screening bash "$PWD/scripts/school_gpu_phase1.sh"
```

`done(...)` 要求前序作业成功退出；GPU 不可见、服务启动失败、输入漂移、环境状态或首轮行为不一致都会使冒烟失败。正式任务此时保持等待，不会绕过冒烟。七组在一道题上失败本身是有效实验结果，不等于基础设施失败。若冒烟因时限退出，也不得把部分结果当作通过。

默认运行编号：`school-smoke-<作业号>` / `school-screening-<作业号>`。同一作业不会覆盖已有运行目录。冒烟的 `summary.json` 必须为 `mode=smoke`、`status=complete`、7/7 单元；首轮核对写入 `task_results.jsonl` 和 `trace.jsonl`。正式结果只有 `full_two_seed_screening=true` 才是完整两种子筛选。

## 查看、停止与证据

```bash
jjobs -u "$USER"
jjobs -l 实际作业号
jhist 实际作业号
tail -n 30 logs/school-smoke-实际冒烟作业号-job/experiment.log
cat logs/school-smoke-实际冒烟作业号/summary.json
```

`PEND` 是等待，`RUN` 才是正在运行。若显示 `Job's GPU resource requirements not satisfied`，表示当前资源申请未获满足，不能据此断言模型有错。正式任务还可能显示前序依赖未满足。

要取消整条链，应先取消正式任务，再取消冒烟：`jctrl kill 实际正式作业号`，然后 `jctrl kill 实际冒烟作业号`，避免冒烟成功后正式任务继续启动。已完成的任务无需取消。

每个 `logs/<run-id>-job/` 保存 GPU 信息、CUDA 设备、预检、服务日志、实验日志和退出记录；`logs/<run-id>/` 保存 manifest、逐步轨迹、逐题结果和 summary。`server.log` 可核对 GPU offload；`job.json` 保存 UniScheduler 作业号、执行节点、CUDA 分配和退出码。总耗时/计费以学校调度器记录为准，不能只统计生成 token 的时间。

调度命令依据[学校一期作业说明](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/job1/)及服务器 `jsub -h`；`gpu` 是官方列出的 A30 队列，见[学校队列表](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/queue/)。
