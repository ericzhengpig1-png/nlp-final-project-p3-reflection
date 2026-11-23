# 文档迁移与环境检查 · 2026-11-22

返回 [文档索引](../README.md) · [交接入口](../../AI_SYNC.md)。本次只整理文档并检查环境，没有执行模型实验、修改实验代码、移动原始日志、删除或重建环境，也没有提交或推送 Git。

## 位置与文件去向

- 当前工作区：`D:/大二上_校内课程/NLP/project/hkust-gz-aiaa-4051-nlp-p3`。
- 主仓库：工作区下 `work/nlp-final-project-p3-reflection`，已由 Git 根目录查询确认。
- 整理前主仓库 Git 工作区干净；旁边的 `p3-clean-checkout` 和上游仓库保持原状。

| 原位置 | 现位置 | 处理 |
| --- | --- | --- |
| docs/baseline.md | [experiments/baseline.md](../experiments/baseline.md) | 移动，正文保持原样 |
| docs/anchor_attempt1.md | [experiments/anchor_attempt1.md](../experiments/anchor_attempt1.md) | 移动，仅修正配置文件相对链接 |
| docs/paper_notes/.gitkeep | papers/.gitkeep | 迁移占位；原目录无论文笔记 |
| AI_SYNC.md 中 2026-11-09、11-10 的历史段落 | [2026-11-09_10.md](2026-11-09_10.md) | 保留历史原文，仅修正文档链接；根入口保留索引 |
| 外部 plan.md、plan.html | [当时的 planning/plan.md](../planning/review-2026-11-22.md)、[planning/plan.html](../planning/plan.html) | 复制，来源文件保留，副本适配导航与路径 |

根目录 README.md、AI_SYNC.md 保留，并修复 data/README.md 的基线链接。新增 [docs/README.md](../README.md)。未覆盖任何已有同名目标文件。

## 复审计划来源

两份均可读取：

- `C:/Users/Lenovo/Documents/Codex/2026-11-22/new-chat/plan.md`
- `C:/Users/Lenovo/Documents/Codex/2026-11-22/new-chat/plan.html`

来源文件完整保留。归档副本保留审阅结论和正文，补充相互导航、当前实验文档与证据包链接；旧审阅目录标记为历史来源，原 Library 入口也保留。

## 环境检查发现

检查对象是工作区的 `work/.p3-venv`，以及仍可访问的旧环境：

`C:/Users/Lenovo/Documents/Codex/2026-11-10/hkust-gz-aiaa-4051-nlp-p3/work/.p3-venv`

通过 Windows 文件属性、reparse point 查询和 WSL Ubuntu-22.04 中的路径检查交叉核对：

| 检查项 | 发现 |
| --- | --- |
| 旧环境 lib64 | 符号链接，目标为相对路径 `lib`，不是普通目录；WSL 确认 `islink=True` |
| 新环境 lib64 | 不存在；不是迁移成了普通目录。WSL 中 `exists=False` 且 `lexists=False` |
| 新环境 lib | 存在，是普通目录 |
| 新环境 bin/python | 符号链接，目标 `/usr/bin/python3`，在 Ubuntu-22.04 中解析到 `/usr/bin/python3.10` |
| 新环境 bin/python3、bin/python3.10 | 都是指向 `python` 的相对符号链接，当前可解析 |
| pyvenv.cfg | `home = /usr/bin`、CPython 3.10.12，属于 Linux/WSL 环境配置 |
| 激活脚本 | `bin/activate`、`activate.bat`、`activate.csh`、`activate.fish`、`activate.nu` 仍写死旧环境绝对路径 |
| 命令入口 | `bin/tw-play`、`bin/alfworld-download` 的首行解释器路径仍指向旧环境 |
| 包路径元数据 | 在 `.pth`、`.egg-link`、`direct_url.json` 中按 `Codex`、`hkust`、`/mnt/c/` 检索，未发现旧项目路径命中 |
| 当前 PowerShell 的 python | 解析为 `C:/Users/Lenovo/anaconda3/python.exe`；没有设置 VIRTUAL_ENV、CONDA_PREFIX、PYTHONHOME、PYTHONPATH |

残留旧路径为：

`/mnt/c/Users/Lenovo/Documents/Codex/2026-11-10/hkust-gz-aiaa-4051-nlp-p3/work/.p3-venv`

因此，使用这些激活脚本或命令入口可能继续调用旧环境；不能将目录复制完成视为运行环境迁移完成。本次没有激活环境、运行实验、删除链接或重建环境，也未验证依赖导入和模型运行。

WSL 启动还输出已有配置提示：Windows `.wslconfig` 中的 `wsl2.hostAddressLoopback` 未识别，以及 Linux `/etc/wsl.conf` 中 `boot.systemd` 重复。路径检查仍成功完成，这些配置未作修改。

## 尚待处理

- 未发现可归档的独立论文阅读笔记，papers/ 当前仅保留占位；没有把实验说明或上游工具文档改称论文笔记。
- Python 环境仍需单独处理旧路径和缺失的 lib64。本次按要求仅报告，不修复或重建。
