# M1 · ALFWorld 与 A/B 基线

课程 `p3.pdf` 的 P3 部分引用公开 ALFWorld 和 ReAct 仓库，要求沿用现有 Reflexion，并验证工作流。PDF 没有给出课程发放包的 tag 或提交。此实现以 [ALFWorld 0.4.2](https://github.com/alfworld/alfworld/tree/1558ba46d078279ecb4c5d33a6cdffc96714a2d2)、TextWorld 1.6.2、[TW-PDDL 2.1.2 数据](https://github.com/alfworld/alfworld/releases/tag/0.4.0)和 [Reflexion 的 ALFWorld 实现](https://github.com/noahshinn/reflexion/tree/218cf0ef1df84b05ce379dd4a8e47f17766733a0/alfworld_runs)为可核验的复现版本。

## 从任务到结果

1. `configs/task_registry.json` 中的相对任务 ID 定位到原始 `game.tw-pddl`。每次尝试新建一个只加载此任务的 TextWorld 环境，使用 ALFWorld 的命名和任务信息包装器，再调用 `reset()`。每次比较初始观察和底层事实的哈希，跨 A/B 也比较。
2. `run_task()` 用原始 Reflexion 的同类示例和 `EnvironmentHistory` 组装动作提示词。固定模型在 `LlamaServer.generate()` 中直接续写原始提示词前缀并返回一行输出。模型输入是任务观察、交互历史和 B 的文本反思。
3. 动作进入 `env.step(command)`，观察回到历史。原示例中的 `put X in/on Y` 转成新版环境的 `move X to Y`，轨迹保存两种写法。思考行获得 `OK.`，单独计入模型回合。每次最多 49 个策略回合、30 个环境动作。
4. 成功只取 TextWorld 的 `state.won`。成功立即退出任务。到动作上限、环境结束、连续重复输出或策略回合上限会结束当前尝试。环境与历史会重新创建，最多尝试 3 次。
5. B 在失败且仍有重试时调用上游 `_generate_reflection_query()`，传入失败轨迹和最多三条已有反思。同一模型生成的新反思进入下一次 `EnvironmentHistory` 的记忆段。A 的记忆列表始终为空。两组共用任务、动作逻辑、示例、模型和种子公式。

上游入口依次是 [main.py 的 trial 循环](https://github.com/noahshinn/reflexion/blob/218cf0ef1df84b05ce379dd4a8e47f17766733a0/alfworld_runs/main.py)、[alfworld_trial.py 的动作循环](https://github.com/noahshinn/reflexion/blob/218cf0ef1df84b05ce379dd4a8e47f17766733a0/alfworld_runs/alfworld_trial.py)、[generate_reflections.py](https://github.com/noahshinn/reflexion/blob/218cf0ef1df84b05ce379dd4a8e47f17766733a0/alfworld_runs/generate_reflections.py) 和 [env_history.py](https://github.com/noahshinn/reflexion/blob/218cf0ef1df84b05ce379dd4a8e47f17766733a0/alfworld_runs/env_history.py)。本项目直接加载上游的示例、历史类和反思提示词生成函数。课程适配包括显式任务 ID、每次重新加载原始游戏、动作预算、同一个开源模型生成动作和反思，以及失败尝试之后只在还有重试时生成反思。原文模型和论文成绩另有其运行条件。

## 1. 安装与下载

从仓库根目录运行。支持 Linux x86_64 的 Python 3.10，Windows 用 Ubuntu 22.04 WSL。若系统要从源码安装 TextWorld 依赖，需要 C/C++ 编译器、CMake 和 Python 开发头文件。Ubuntu 可通过 `build-essential cmake python3-dev` 安装，学校节点用已有的软件模块或环境。

```bash
uv venv --python 3.10
uv pip sync --python .venv/bin/python requirements-baseline.txt
.venv/bin/python scripts/setup_baseline.py
```

准备脚本校验 TW-PDDL 压缩包哈希，仅取登记的开发任务。Reflexion 从固定提交下载并校验每个使用的文件。可用 `--archive /path/to/json_2.1.2_tw-pddl.zip` 复用已下载的数据包。任务只使用官方 TW-PDDL 文件，无需 THOR 或检测器权重。

## 2. 先验证环境

```bash
.venv/bin/python scripts/run_baseline.py manual --run-id manual-01 --commands configs/tutorial_actions.txt
.venv/bin/python -m unittest discover -s tests -v
```

去掉 `--commands` 可自己输入动作。教程应该显示第 4 个动作后的 `won=True`。回归测试在真实 ALFWorld 游戏上用预定动作检查三个失败尝试各停在 30 个环境动作、拾取后的状态在重试时恢复、A/B 首次提示一致、B 的记忆进入重试，以及成功后立即停止。测试里的动作和反思是测试输入，模型试跑单独运行。

## 3. 启动模型，先跑两任务

下载固定的 [Qwen2.5-1.5B-Instruct Q4_K_M GGUF](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9) 和 [llama.cpp b12244](https://github.com/ggml-org/llama.cpp/releases/tag/b12244)。Linux GPU 选与计算节点驱动兼容的发布包，CUDA 12.8 预编译包需要同版本运行库或兼容的系统安装。Windows 本地可用对应的 Windows Vulkan 包，将服务运行在 Windows，ALFWorld 运行在 WSL。本次配置用 8192 词元上下文，动作和反思分别最多 128 和 256 词元。每个任务的环境种子固定为 4051，模型种子为 `4051 + 1000 * (attempt - 1) + policy_turn`，反思使用该尝试的偏移 999。

```bash
.venv/bin/python scripts/setup_baseline.py --model
/path/to/llama-server --list-devices
mkdir -p logs
.venv/bin/python scripts/serve_model.py --llama-server /path/to/llama-server --device CUDA0 2>&1 | tee logs/llama-server.txt
```

如果模型下载需要镜像，可以为下载步骤设置 `HF_ENDPOINT`，权重仍须通过同一 SHA-256 校验。设备名用 `--list-devices` 的结果。在有该 GPU 分配的计算节点内运行服务和实验。服务使用本机回环地址，启动脚本会核对二进制版本和权重哈希。

模型服务就绪后，在同一机器的另一个终端运行：

```bash
.venv/bin/python scripts/run_baseline.py pilot --run-id dev-pilot-01
```

核对 `logs/dev-pilot-01/summary.json` 与 `trace.jsonl`，确认 A/B 每个任务都有结果、同任务的重置哈希一致，并检查 B 首次失败后的 `reflection` 和下一次 `reset.memory`。模型成功率可以是零，流程仍可通过这些检查。通过后扩大到清单里的全部 10 项：

```bash
.venv/bin/python scripts/run_baseline.py dev --run-id dev-ab-01
```

已存在的运行编号会被拒绝，错误或中断的运行保留已有轨迹并记录 `run_error`。在共享服务器留存 `nvidia-smi`、模型服务启动日志和 GPU 分配记录。用调度器的分配时长 × GPU 数量记项目预算，模型服务的推理耗时用于比较 A/B 的模型开销。

## 课程 GPU

[港科广 HPC 官方一二期入口](https://hpc2login.hpc.hkust-gz.edu.cn/)和[连接说明](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/connection/)可用于找门户 Terminal。先通过课程确认账号对应的集群和允许的 GPU 分区。在终端执行 `hostname; command -v srun; nvidia-smi -L`。若是 Slurm 登录节点，按课程分区申请一张卡的短交互作业，再在计算节点运行上面的步骤。若门户已经分配容器，可在容器终端核对 GPU 后执行。记下分区、作业编号和实际卡型，验证通过后再扩大任务数。

## 本地验证记录 · 2026-11-10

- `m1-manual-clean-20261110` 在提交 `e4e92bc` 下完成四动作放书教程，末步 `won=True`，耗时 1.52 秒。另从 GitHub 新克隆一份功能分支，重新下载数据与提示词，通过同一教程。
- `m1-pilot-20261110` 是早期聊天模板试跑。模型经常输出解释或确认语，两组累计成功均为 0/2。保留该次轨迹用于排查提示词接入。
- `m1-pilot-raw-20261110` 在提交 `9b3ca7b` 下用同一原始提示词前缀直接续写。平台为 WSL Ubuntu 22.04 加 Windows RTX 5060 Laptop GPU，llama.cpp b12244 Vulkan。两任务端到端耗时 185.44 秒。

| 条件 | 首次成功 | 三次内成功 | 恢复 | 模型调用 | 输入 / 输出词元 | 后端推理秒数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 0/2 | 0/2 | 0/2 | 238 | 497812 / 3148 | 88.58 |
| B | 0/2 | 2/2 | 2/2 | 116 | 250459 / 2351 | 50.31 |

**放书任务的 B 组重试。** 在 `m1-pilot-raw-20261110/trace.jsonl` 搜索 `trial_T20190908_050633_745514`。尝试 1 打开抽屉 1 只看见手机，随后仍尝试从该抽屉取书，环境回 `Nothing happens.`，第 30 个动作触发上限。反思建议继续查抽屉，并提出从抽屉取书。尝试 2 的重置哈希与尝试 1 相同，抽屉再次为关闭状态，文本反思出现在第一个模型请求里。模型随后去了餐桌，从观察中找到并拾起书 3，第 8 个环境动作成功放到边桌。反思对书的位置缺乏观察证据，实际成功路径用了重试中新获得的观察。

`m1-dev-ab-20261110` 使用同一提交、模型和配置，完成固定的 10 个开发任务，端到端耗时 590.93 秒。

| 条件 | 首次成功 | 三次内成功 | 恢复 | 模型调用 | 输入 / 输出词元 | 后端推理秒数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 4/10 | 6/10 | 2/6 | 566 | 1127604 / 5956 | 190.79 |
| B | 4/10 | 6/10 | 2/6 | 547 | 1205256 / 8239 | 223.43 |

10 个任务的 A/B 首轮动作输出和种子一致。40 次尝试中，28 次在第 30 个环境动作停止，12 次收到 `won=True` 后停止。B 生成 10 条反思，逐条核对了下一次尝试的记忆和模型输入。两组各恢复 2 个任务，A 恢复冷却盘子和灯下检查 CD，B 恢复放书和清洁黄油刀。

证据包 `p3-m1-baseline-evidence.zip` 含两个阶段的完整轨迹、运行清单和核对记录。PR 中引用运行编号和团队共享存放位置，给队友留出原始轨迹的访问入口。
