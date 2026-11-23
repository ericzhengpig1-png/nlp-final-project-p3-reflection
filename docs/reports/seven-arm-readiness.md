# 七组入口与学校 GPU 脚本：就绪检查

日期：2026-11-23（北京时间）。交付分支：`feat/seven-arm-school-gpu`。

实现提交：[02528bf](https://github.com/ericzhengpig1-png/nlp-final-project-p3-reflection/commit/02528bf9c01418015a0f0fb3486569591b3cd945)，已推送并核对远端完整 SHA 与本地一致。后续交接记录提交不改变实验代码。

**结论：七组开发入口、学校 Slurm/容器脚本和无模型检查已完成。未启动本地模型，未连接或提交学校实验，新增 GPU 用量为 0。** 本报告证明协议实现和脚本生命周期检查通过，不提供 S1–S5 的真实效果或学校性能结论。

## 实现范围

| 内容 | 具体实现 |
| --- | --- |
| 共用七组入口 | `scripts/run_experiment.py` 调用既有 `run_baseline.run_task`；A 无反思，B 调用原查询，S1–S5 只替换完整指令前缀 |
| 固定实验输入 | `configs/seven_arm.json` 记录基线配置、任务 registry、六份指令的 SHA-256；文本按 UTF-8/LF 校验 |
| 调度 | 10 个开发任务 × 7 组 × 4051/4052 = 140 单元；每题轮转组序，4052 独立运行时仍偏移一位 |
| 控制变量 | 原 actor/反思示例与记忆规则、3 尝试、30 环境动作、49 回合、128/256 输出 token、逐请求种子公式和成功即停 |
| 首轮核对 | 比较同题同种子的空记忆、初始状态、请求哈希/种子、输出、动作/状态和结束原因；不一致保存证据并停止 |
| 证据与汇总 | manifest、完整 trace、逐单元 task_results、summary；逐种子成功/恢复、相对 A/B 配对 W/L、跨种子平均与成本 |
| 失败处理 | 已完成结果立即追加，摘要原子写入；失败/中断明确标记，不把未完成单元计为任务失败，不覆盖 run ID |
| 学校脚本 | Slurm GPU 分配检查、CUDA0 检查、可配置端口、服务就绪超时、独立进程组清理；单模型服务串行执行七组 |

原 `baseline.json` 与五份候选指令正文均未改动；原 A/B 命令兼容。历史 Anchor 入口不参与本轮。30 题留出集不执行，最终 C 未选择。

## 验证结果与具体证据

运行环境为现有 WSL Ubuntu 22.04 / Python 3.10.12 / ALFWorld 0.4.2 / TextWorld 1.6.2。直接调用迁移后的虚拟环境 Python，无需改动旧 activation 路径。以下命令在仓库根目录执行，`python` 指该解释器。

| 检查 | 结果 |
| --- | --- |
| `python -m unittest discover -s tests -v` | 当时全部 25 个用例通过，43.296 秒 |
| 增加 CPU-only Slurm 分配拒绝检查后：`python -m unittest discover -s tests -p test_school_gpu.py -v` | 相关 11 个用例全部通过，8.180 秒；最终测试集共 26 个用例，其余文件未再改动 |
| `python scripts/run_experiment.py --check-only` | `passed`，7 组 / 10 题 / 2 种子 / 140 单元，`model_requests: 0` |
| `bash -n scripts/run_school_gpu.sh scripts/school_gpu.sbatch` | 通过 |
| Git diff 空白检查 | 通过 |
| 提交后从本地 Git 历史新克隆到临时 Linux 目录，复用既有数据/上游文件执行预检与 Bash 语法检查 | 通过，Git 工作区干净；验证 Git 中的 LF 文件与全部冻结哈希一致，没有启动模型 |

测试文件为 [test_screening.py](../../tests/test_screening.py)、[test_school_gpu.py](../../tests/test_school_gpu.py) 及原 baseline/Anchor 测试。新测试未使用真实模型服务；完整调度使用模拟任务，学校生命周期使用临时假 GPU 命令、假服务和假实验进程。

具体案例：

1. **真实文本环境的放书任务。**固定动作先去床 1、拾取 book 1，再交替 inventory/look 直到上限。七组均产生 `[false, false, false]`，各尝试 30 个环境动作；每次初始状态哈希一致。A 始终无反思；B/S1–S5 各生成两条固定测试反思，第三次尝试记忆长度为 2；每组第一次尝试记忆为空，首轮 30 次请求完全一致。这证明重置、预算及记忆隔离，不是模型失败率测量。
2. **原版与候选提示词。**输入相同失败轨迹和已有计划，B 生成结果与上游逐字相同；每个 S 都等于“该候选完整指令 + B 去除原指令后的完整后缀”。上游前缀改变会报错。因此原两份示例、轨迹、既有计划与 `New plan:` 都保留。
3. **完整调度。**模拟 140 单元恰好各出现一次，摘要 complete、每种子每组 10 题；单独 4052 的 70 项顺序等于完整调度的后 70 项。模拟结果仅存在临时测试目录，未作为实验结果提交。
4. **部分失败。**第 2 单元抛异常或模拟中断后，第 1 单元仍留在 JSONL 和摘要；完成数为 1，请求数包含第 2 单元已发出的请求，完整均值为空。故障不会被填成 139 个失败任务。
5. **服务清理。**假实验退出码 7 时包装脚本也返回 7，假模型服务及其子进程结束；发送 SIGTERM 后返回 143，假实验留下部分结果标记。端口占用、无分配、CPU-only 分配、无 CUDA、服务启动失败或超时都不会继续启动实验。

上游 TextWorld 1.6.2 读取游戏时产生 `ResourceWarning: unclosed file`，测试结果仍通过；此次未修改固定上游依赖。首次策略回合上限测试因测试回复完全重复，触发原版 repeated_action；已改为不同的固定思考文本验证 49 回合，不改变生产停止规则。

## 历史证据与文本保持不变

| 文件 | SHA-256 |
| --- | --- |
| `configs/baseline.json` | `5edb6c26f616cec8a76586ced9a9b0681375101f86582de9bac619f1c251ef44` |
| 原十题 A/B `trace.jsonl` | `5785a47257783ebaab2106b8323a4cad03d6bb476b6acb2be70ccbd0f9bb2235` |
| 原十题 A/B `summary.json` | `715df17bbb1dda3450ec1af3a4f41af7c8f4352dce3a0971d22e7abfa93aa5ba` |

六份指令的完整哈希见 [seven_arm.json](../../configs/seven_arm.json)，与本轮实施前一致。原始轨迹仍只在既有日志位置；不上传模型、下载数据或整份原始大日志。此前整理的研究计划、错误分类、论文依据和提示词对照随相关文档一并提交，历史说明的移动保留内容。

## 学校仍需验收的部分

课程实际分区/account/QoS、余额、节点 OS/驱动兼容性、资源下载和真实 CUDA 推理吞吐尚未远端验收。脚本已具备部署条件，但不能据无模型测试宣称学校实跑成功。SIGKILL/节点故障无法保证退出清理函数执行，须根据调度器与已经写出的 JSONL 判断状态。

下一步按[学校 GPU 流程](../experiments/school-gpu-runbook.md)在学校安装与预检；用户决定预算后再提交作业。该流程的准备步骤与真正启动命令明确分开，默认不会启动任何实验。
