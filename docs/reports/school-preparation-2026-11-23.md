# 学校端准备：下载问题处理与无模型验收

2026-11-23（北京时间）。本次经 SSH 连接实际课程账号完成数据和 Python 环境准备，未启动模型服务、未提交任何 GPU 作业。

## 实际平台

- SSH 入口为 `hpc1login.hpc.hkust-gz.edu.cn`，登录节点为 `yq_mgt02`，属于 HPC 一期。
- 系统为 RHEL 8.4、x86_64、glibc 2.28；虚拟环境 Python 3.10.22，ALFWorld 0.4.2、TextWorld 1.6.2。
- 项目路径为 `$HOME/p3-work/repo`，分支 `feat/seven-arm-school-gpu`；本次测试的代码提交为 `6e37a916b8ce96b0f28633a07271b57a6f0ccd53`。
- `jqueues` 可正常查询；虽然安装了 Slurm 20.11.8，`sinfo` 无法解析其控制器 `mgt02`。后续应使用一期的 UniScheduler / `jsub`，不能直接套用二期 `sbatch`。这是本次实际连接后的新证据，与[学校一期说明](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/job1/)一致。

## 下载错误与处理

`setup_baseline.py --model` 在获取 ALFWorld 数据包时失败。远端 `curl` 复核显示 GitHub 返回 302，但转到 `release-assets.githubusercontent.com:443` 后 TLS 连接失败；原 Python 错误为 `Connection reset by peer`。目前只确认这条下载连接不可用，未认定具体网络策略原因。

本机已有固定版本的原始数据包、GGUF 和五个 Reflexion 上游文件。先逐一与 `configs/baseline.json` 的 SHA-256 比对，再通过 SCP 上传到学校，远端重新校验后放入原脚本预期位置。随后原样执行 `.venv/bin/python scripts/setup_baseline.py --model`，利用已校验缓存完成准备，没有修改版本、下载 URL、证书校验或实验参数。

| 资源 | 大小 / 数量 | 验证 |
| --- | --- | --- |
| `json_2.1.2_tw-pddl.zip` | 36,493,542 字节 | 与冻结 SHA-256 一致 |
| Qwen2.5-1.5B-Instruct Q4_K_M GGUF | 1,117,320,736 字节 | 与冻结 SHA-256 一致 |
| Reflexion 上游文件 | 5 个，包括 actor JSON 与反思示例 | 全部与冻结 SHA-256 一致 |
| 提取后的开发任务 | 10 个 `game.tw-pddl` | 原准备脚本提取，七组预检通过 |

这里完成的是离线资源准备；服务器到 GitHub 资源域名的网络问题本身没有被修改或宣称修复。本地只校验和传输文件，没有运行模型。

## 学校端实际检查

| 检查 | 结果 |
| --- | --- |
| `scripts/setup_baseline.py --model` | `Assets ready for 10 development tasks.` |
| `scripts/run_experiment.py --check-only` | passed，7 组、10 题、2 种子、140 单元，`model_requests: 0` |
| `python -m unittest discover -s tests -v` | 26 个用例通过，59.168 秒；固定回复、CPU 文本环境和临时模拟进程 |
| `uv pip check --python .venv/bin/python` | 71 个包，全部依赖兼容 |
| `git status --short` | 测试后工作区干净 |
| `jjobs -u "$USER"` | `No unfinished job found`；本次没有提交作业 |

测试保留了上游 TextWorld 的已知 `ResourceWarning: unclosed file`，没有影响通过结果。本次未修改上游代码。

学校端证据位于 `$HOME/p3-work/repo/logs/preparation-20261123/`：`assets.json`、`preflight.json`、`preflight.err`、`protocol-tests.log`、`dependencies.log`、`jobs-after.txt`、`summary.json`。日志与大型资产不进 Git；连接凭据不写入仓库或报告。

## 后续开跑前仍需完成

1. 将学校作业入口适配到本账号实际使用的 HPC 一期 UniScheduler，保留同一七组循环与清理规则。现有 `school_gpu.sbatch` 是二期模板；不要通过伪造 `SLURM_JOB_ID` 或设置 `P3_CONTAINER=1` 在一期登录节点绕过保护。
2. 准备并验证兼容学校 Linux 环境的 llama.cpp b12244。当前未准备该 Linux 推理运行库，也未测试 CUDA 推理；不能仅凭已上传 GGUF 就称完整推理环境已就绪。
3. 由用户决定 GPU 预算和实际运行时限，再提交实验。本次状态为 **assets_and_python_ready**，模型与 GPU 实验启动数均为 0。
