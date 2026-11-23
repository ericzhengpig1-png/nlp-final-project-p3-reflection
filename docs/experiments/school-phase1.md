# 学校 HPC 一期：S1 / S4 优先短作业

2026-11-23 最新决定：先比较 **A（无反思）、B（原反思）、S1（观察证据）、S4（剩余目标）**。S2、S3、S5 暂不提交。优先级来自[原调研记录](../papers/reflection-remedies-2026-11-23.md)，并非已验证的效果排名。

**队列实测更新：使用 `ai` 队列及 `-gpgpu '1 mig=2'`（一个 A30 12GB MIG 实例）。** 文档列出的 `gpu` 队列目前只含 g-node02/g-node04，调度器没有登记其 GPU 资源；`ai` 包含启用 MIG 的 g-node01。设备检查作业 30559 已成功。原冒烟 30537 首次获分配后因缺少 `CUDA_VISIBLE_DEVICES` 被保护脚本拦下；一期入口现从调度器的 `JH_GPU_RANK` 读取本作业、本节点的单个设备 UUID，拒绝冲突或多设备记录，不手动选择空闲卡。

MIG 计算环境还缺少 Git。学校共享目录 `$HOME/p3-work/runtime-tools/` 已放置登录节点的 Git 2.27 和其非 glibc 依赖（libpcre2、libz、libcrypto），用于 `status` / `rev-parse` 内建命令；SHA256SUMS 同目录留档。入口增加这些路径，Git 缺失或检查失败时在模型启动前退出，不能将空输出当成干净工作树。模型服务的 action/prompt CPU 线程数均使用申请到的 4 核。

## 范围与时限

| 阶段 | 内容 | 资源与上限 |
| --- | --- | --- |
| 独立冒烟 | 第一题、4051、四组，4 单元 | 1 个 12GB MIG 实例，10 分钟 |
| 正式分批 | 每批一道题、一个种子、四组；10 题 × 2 种子，共 20 批、80 单元 | 每批 1 个相同规格的 MIG 实例，10 分钟，串行成功依赖 |
| 合并 | 完整性、版本与首轮审计校验，然后配对汇总 | 1 CPU，5 分钟，不申请 GPU |

20 批正式作业的实例运行时限合计最多 200 分钟，另加 10 分钟冒烟；MIG 计费和实际占用以学校调度记录为准。时限不是预计耗时，超时会停止后续依赖，不能把未完成批次算作失败样本。短作业是否更快获分配仍取决于队列资源。

复用冻结协议中的模型、提示词、采样、每题动作与重试预算。从原七组轮转顺序中过滤出本轮四组；分批使用全局题号，避免每批都重新从 A 开始。不同组的环境和记忆独立重置。冒烟与正式结果分目录保存。

## 当前账号与固定运行库

入口为 `hpc1login.hpc.hkust-gz.edu.cn`，实际登录节点 `yq_mgt02`，调度器 UniScheduler。使用 `jsub`；本账号不用二期 `sbatch` 模板。已提交批作业由调度器管理，关闭 SSH 不会取消作业。

llama.cpp 源码固定为 `b12244` / `d5bbcd1f31dba754f716a26c3a4784502a6b9ede`。`git archive HEAD` 的 LF tar SHA-256 为 `96bccbdea51ea9774292e1b90b5a7c5945985f6bc4a02c91f23801b8508fb1ea`。

学校 GCC 编译发现上游 `server-context.cpp` 使用 `std::setw` 却缺少 `<iomanip>`；仅补充这个标准头文件，补丁见 [llama-b12244-iomanip.patch](../../patches/llama-b12244-iomanip.patch)。不改推理逻辑、提示词或采样。原始构建还发现 CMake 的 `cc/c++` 自动指向系统 GCC 8，因此最终显式指定 GCC 12.1。全部四组/批次共用修复后的同一运行库，manifest 记录二进制及共享库组合哈希、GPU 型号与驱动；汇总拒绝它们不一致。

以下构建命令仅在学校 CPU 计算作业运行：

```bash
source /hpc/jhinno/modules-4.2/init/bash
module load gcc-12.1.0 cuda-12.8 cmake-3.24
cd "$HOME/p3-work/llama.cpp-b12244"
mkdir -p "$HOME/p3-work/cuda-link-stubs"
ln -sfn /hpc/jhinno/cuda/cuda-12.8/targets/x86_64-linux/lib/stubs/libcuda.so "$HOME/p3-work/cuda-link-stubs/libcuda.so.1"
cmake -S . -B build-cuda-gcc12 -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath-link=$HOME/p3-work/cuda-link-stubs" \
  -DCMAKE_C_COMPILER=/hpc/software/gcc-12.1.0/bin/gcc \
  -DCMAKE_CXX_COMPILER=/hpc/software/gcc-12.1.0/bin/g++ \
  -DCMAKE_CUDA_HOST_COMPILER=/hpc/software/gcc-12.1.0/bin/g++ \
  -DGGML_CUDA=ON -DGGML_NATIVE=OFF -DCMAKE_CUDA_ARCHITECTURES=80 \
  -DLLAMA_BUILD_NUMBER=12244 -DLLAMA_BUILD_COMMIT=d5bbcd1f \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
  -DLLAMA_OPENSSL=OFF
cmake --build build-cuda-gcc12 --target llama-server --parallel 8
```

归档没有 `.git`，显式 build number/commit 与真实原始源码一致。默认运行库是上述 `build-cuda-gcc12/bin/llama-server`；运行时加载相同 GCC/CUDA 模块。构建选项参考[固定版本官方说明](https://github.com/ggml-org/llama.cpp/blob/b12244/docs/build.md)。

CPU 编译节点没有 NVIDIA 驱动库，因此最终链接使用 CUDA toolkit stub 的 SONAME 链接和仅链接期的 `-rpath-link`。自建 `cuda-link-stubs` 目录不会加入 GPU 作业的 `LD_LIBRARY_PATH` 或运行期 RPATH。CMake 自带 RPATH 包含 toolkit 的 stubs 目录，但该目录没有 `libcuda.so.1`；所需驱动须由 GPU 节点提供，实际版本与 GPU offload 在冒烟中验证。服务器直连 GitHub 不稳定时，可通过 SCP 传输 `git bundle` 并 fast-forward 到同一提交，不改变代码版本。

## 提交

在学校仓库根目录完成同步和无模型预检。每次使用新 campaign ID，避免重复申请；从提交到整轮结束，不要修改此目录的代码或运行库。

```bash
cd "$HOME/p3-work/repo"
git status --porcelain
.venv/bin/python scripts/run_experiment.py --check-only --smoke --conditions A B S1 S4
.venv/bin/python scripts/run_experiment.py --check-only --task-index 0 --seeds 4051 --conditions A B S1 S4
export P3_CAMPAIGN=priority-s1s4-新的唯一编号
# 编译仍在进行时可设置 P3_BUILD_JOB=实际编译作业号；已完成则不用设置。
bash scripts/submit_priority_phase1.sh
```

提交脚本依次提交四组冒烟、20 个正式短作业以及 CPU 合并作业。每个作业依赖前一个 `done(作业号)`，任一阶段异常退出则后续不会运行；成功或失败的任务结果本身不是基础设施异常。提交失败时保留已返回的作业号，不自动重试或重复提交。

GPU 检查、服务启动、版本和输入校验、环境重置/首轮一致性检查都保留。冒烟通过要求 `mode=smoke`、`status=complete`、4/4 单元；一个任务上的结果只用于验证流程。

## 状态、证据与停止

```bash
jjobs -u "$USER"
jjobs -l 实际作业号
cat logs/实际campaign-submission/jobs.tsv
tail -n 30 logs/实际campaign-smoke-job/experiment.log
cat logs/实际campaign-smoke/summary.json
cat logs/实际campaign-merged/summary.json
```

`PEND` 表示等待，`RUN` 才表示运行。`Job's GPU resource requirements not satisfied` 表示 GPU 申请未满足；`Waiting for job dependency to be satisfied` 表示前序尚未成功。目录在对应程序启动后才出现。

- `logs/<campaign>-submission/`：提交时 Git SHA、GPU 作业表和 CPU 合并作业号。
- `logs/<campaign>-smoke/`：独立冒烟轨迹和摘要。
- `logs/<campaign>-s4051-t0/` 等：每批 manifest、trace、task_results、summary。
- 每个运行对应的 `-job/`：GPU 信息、预检、server.log、experiment.log、退出记录。
- `logs/<campaign>-merged/`：20 批来源及哈希、80 单元、四组配对指标。`full_two_seed_screening=false`，因为 S2/S3/S5 尚未运行；四组完整性由 80/80 和条件列表确认，不能称作七组完成。

合并拒绝缺失、重复、不完整、混入冒烟、首轮审计不一致或不同代码/配置/提示词/运行库/GPU 型号/驱动的批次。失败/重跑消耗和调度占卡时长另报，不用成功批次的生成耗时代替总预算。

如需停止整轮，先取消合并及后续等待批次，再取消最前面的活动任务，使用 `jctrl kill 作业号`；ID 从 submission 目录读取。不要重新执行同一 campaign 的提交脚本，也不要在普通登录节点手动启动模型。

命令依据[学校一期作业说明](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/job1/)及服务器 `jsub -h`；官方[队列表](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/queue/)仍列 `gpu`，本次改用可实际调度的 `ai` / MIG 入口。A30 的 `2g.12gb` 规格见 [NVIDIA 文档](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/supported-mig-profiles.html)，通过 UUID 设置可见设备见 [CUDA 文档](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html)。
