# 文档索引

返回 [仓库入口](../README.md) · [当前交接入口](../AI_SYNC.md)。

| 分类 | 文档与位置 | 用途 |
| --- | --- | --- |
| 宏观计划 | [planning/plan.md](planning/plan.md) | 2026-11-23 研究与执行计划：问题、假设、最小实验、阶段验收、预算与报告 |
| 历史计划 | [重写前计划](planning/plan-before-rewrite-2026-11-23.md) | 保留上一版全文，追溯已确认的课程范围与协作约定 |
| 研究报告 | [R00 十题基线复核](reports/R00-baseline.md) | 每步报告的实例，含逐题配对图和原始证据 |
| 研究报告 | [C01-01 轨迹分析与小试建议](reports/C01-01-design.md) | 全部 10 条 B 反思标注、英文提示词草案与分阶段预算；本轮 GPU 为 0 |
| 错误分类 | [五类反思错误](experiments/reflection-error-taxonomy.md) | 事实、归因、更新、剩余目标、信息密度的统一定义、案例与判断边界 |
| 文献与方案 | [反思改进文献与候选](papers/reflection-remedies-2026-11-23.md) | 对照论文和作者 GitHub 的五个提示词候选、课程适配、依据与局限；均未实验 |
| 提示词草案 | [S1–S5 完整提示词与案例推演](reports/S1-S5-prompt-drafts.md) | 五份完整英文指令、B 原版对照、盘子与锅铲的十份人工期望示意；均未实验 |
| 实验规划 | [A/B/S1–S5 七组筛选](planning/seven-arm-screening.md) | 七组同十题、同两种子比较；变量控制、提升判据、参考预算与运行前准备；待执行 |
| 学校 GPU | [上传与远端运行流程](experiments/school-gpu-runbook.md) | 七组入口已接入；学校部署、Slurm/容器脚本、预检与日志回收；尚未启动实验 |
| 实现验收 | [七组与学校脚本就绪检查](reports/seven-arm-readiness.md) | 无模型协议测试、140 单元模拟、服务失败/中断清理与实际远端待验收项 |
| 历史复审 | [11 月 22 日完整复审](planning/review-2026-11-22.md) | 当时的审阅结论、原定排期与证据索引 |
| 历史复审 | [planning/plan.html](planning/plan.html) | 可在浏览器打开的一页项目速览 |
| 实验说明 | [experiments/baseline.md](experiments/baseline.md) | ALFWorld 安装、A/B 基线复现、已运行结果与证据 |
| 实验说明 | [experiments/anchor_attempt1.md](experiments/anchor_attempt1.md) | Anchor 尝试 1 的方法、运行步骤与结果 |
| 论文笔记 | [papers/](papers/) | 文献依据与作者实现笔记；已有五类反思错误的改进方案调研 |
| 历史交接 | [handoffs/2026-11-09_10.md](handoffs/2026-11-09_10.md) | 从 AI_SYNC.md 归档的历史快照、M1 本地复现与 Anchor 交接原文 |
| 迁移记录 | [handoffs/migration_2026-11-22.md](handoffs/migration_2026-11-22.md) | 本次文件去向、计划来源、lib64 与 Python 路径检查发现 |
| 技术决定 | [decisions/](decisions/) | 保留原有目录与占位，供后续记录技术决定 |

历史复审的 Markdown 和 HTML 复制自 `C:/Users/Lenovo/Documents/Codex/2026-11-22/new-chat/`，来源文件保留；副本仅补充导航和迁移后的路径。文档中的实验命令仍按仓库根目录执行。

原始轨迹仍在仓库 `logs/`，定位方式见 [日志索引](../logs/README.md)；证据包仍在工作区 `outputs/`。当前迁移环境存在旧路径引用，检查结果见迁移记录。
