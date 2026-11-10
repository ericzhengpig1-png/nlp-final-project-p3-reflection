# 数据与任务划分

任务文件来自 ALFWorld 发布的 `json_2.1.2_tw-pddl.zip`，包内目录名为 `json_2.1.1`。版本和压缩包哈希见 `configs/baseline.json`，获取步骤见 [M1 基线说明](../docs/baseline.md)。

`configs/task_registry.json` 在查看模型表现前固定。开发集取 `valid_seen`，留出集取 `valid_unseen`。只纳入上游标记为可解的游戏，按上游规则排除 movable 和 Sliced 任务。开发集先从放置、清洁后放置两类各取字典序最早的 ID 作试跑任务。其余任务按类型名称排序轮询，每类内部按 `sha256("4051:" + task_id)` 排序取样。留出集 30 项全部用同一轮询规则。

教程和两任务试跑都属于开发集。清单作为本轮复现基准，由团队在 Notion 确认是否纳入正式协议。准备脚本只提取开发集任务，原始数据不提交到仓库。
