# Seven-arm School GPU Implementation Plan

> **For agentic workers:** Use the writing-plans execution checklist below task by task. 本轮用户已明确要求直接完成实现、检查并提交，主会话执行，不另设审批或实验启动步骤。

**Goal:** 接入 A/B/S1–S5、学校 GPU 作业入口，完成无模型检查并推送独立 GitHub 分支。

**Architecture:** 七组共用 `run_baseline.run_task`，只替换反思指令前缀。新入口负责冻结资源、双种子轮转、配对汇总和失败留档；学校包装脚本负责资源检查、服务就绪与进程清理。

**Tech Stack:** Python 3.10、unittest、Bash、Slurm；既有 ALFWorld/TextWorld 与 llama.cpp 配置。

**Spec:** [七组筛选协议](seven-arm-screening.md)

## Global Constraints

- 固定开发集 10 题、A/B/S1/S2/S3/S4/S5、种子 4051/4052，共 140 单元。
- 单种子可分轮提交；轮转偏移由种子在冻结清单中的索引决定，4052 单独运行也偏移一位。
- 保留原 actor、示例、记忆、30 动作 / 49 回合 / 3 尝试与成功即停；保持 baseline.json 原样。
- B 使用原查询；S 仅换已写好的完整指令；不注入案例答案，不接入历史 Anchor。
- 不启动本地模型、不提交学校作业；测试只用固定回复、模拟 HTTP/进程与 CPU 文本环境。

## Review Focus

- 指令或上游前缀漂移：哈希/前缀检查拒绝运行。
- 单独跑第二种子：仍沿用冻结顺序，不重新编号。
- 首轮输出不同：保留差异证据并停止，不能视为反思收益。
- 部分中断/重复运行编号：保留已完成单元、明确 incomplete，拒绝覆盖。
- GPU 服务未就绪、端口冲突或运行失败：退出非零并清理本作业启动的进程。

## Task 1 — 七组入口

Files: `src/reflection/instructions.py`, `scripts/run_baseline.py`, `scripts/run_experiment.py`, `configs/seven_arm.json`, `tests/test_screening.py`。

Interfaces: `reflection_prompt(query, scenario, memory, instruction)` 只替换原指令；`run_task(..., reflection_instruction=None)` 保持原 A/B 调用兼容；CLI `run_experiment.py --check-only` 或 `--run-id ID [--seeds 4051 4052] --server URL`。

- [x] 写测试：原 B 原样；S 保留所有后缀；错误前缀拒绝；140 单元无重复、种子轮转一致；恢复率零分母为 null。
- [x] 实现冻结输入、共用循环、首轮一致性、逐单元 JSONL、失败摘要、配对胜负与成本。
- [x] 用固定回复检查真实文本环境中的重置、记忆隔离、成功即停；模拟完整 140 单元和中断。

## Task 2 — 学校脚本

Files: `scripts/serve_model.py`, `scripts/run_school_gpu.sh`, `scripts/school_gpu.sbatch`, `.gitattributes`, `tests/test_school_gpu.py`。

Interfaces: `serve_model.py --port PORT`；包装脚本消费 `P3_SERVER/P3_RUN_ID/P3_PORT/P3_SEEDS`，默认要求 Slurm 分配，学校已分配容器需显式 `P3_CONTAINER=1`。

- [x] 给模型服务增加端口参数并验证范围；保持旧默认 8080。
- [x] 实现 GPU/干净仓库/端口预检、模型服务等待、退出清理；批作业仅提供模板，不执行 sbatch。
- [x] `bash -n`；模拟服务进程测试正常退出、异常退出、超时与信号清理，无真实权重。

## Task 3 — 交付

Files: `docs/experiments/school-gpu-runbook.md`, `README.md`, `AI_SYNC.md`, `docs/reports/seven-arm-readiness.md`。

- [x] 更新可复制学校命令，区分准备、未来提交、状态查看及日志回收。
- [x] 完成自检：原配置/提示词不变；历史数据不变；无模型、凭据或原始大日志入库。
- [x] Git 交付：实现提交 `02528bf9c01418015a0f0fb3486569591b3cd945` 已推送至 `feat/seven-arm-school-gpu`，远端 SHA 核对一致；最终交接记录以本分支历史为准。
