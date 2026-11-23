# 学校 GPU 队列诊断与 MIG 冒烟

## 定位结论

原 `gpu` 队列的候选主机只有 `g-node02`、`g-node04`，两台在调度器中的 `GPUS` / `ngpus` 都显示 `-`。这表示当前没有登记可分配的 GPU 资源，不能据此断言物理显卡不存在。原选择符合[学校公开队列表](https://docs.hpc.hkust-gz.edu.cn/docs/hpc12/slurm/queue/)，但实际运行配置需要进一步核对。

| 实际测试 | 结果 |
| --- | --- |
| `gpu`，申请 1 张完整 GPU | PEND，两个候选节点 GPU 资源未满足 |
| `ai_excl`，申请完整 GPU | PEND，同时报告 GPU 资源不足、一个节点负载信息不可用、两个节点的用户主机绑定限制 |
| `ai`，申请完整 GPU | PEND，三个候选节点资源未满足 |
| **`ai -gpgpu '1 mig=2'`** | **成功分配到 `g-node01`，A30 MIG 2g.12gb** |

`ai` 的主机组包含 g-node01/02/04；g-node01 启用 MIG。已成功完成检查任务 30559（分配标识）与 30560（计算环境 Git）。这说明平台仍能调度 GPU，当前可用路径是 `ai` 的 MIG 资源，不能把原队列“0 RUN”理解成全平台停止运行。MIG 规格依据 [NVIDIA A30 支持表](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/supported-mig-profiles.html)。

## 冒烟中修复的问题

1. **设备分配环境变量不同。** UniScheduler 提供 `JH_GPU_RANK=1;g-node01:MIG-...;`，没有 `CUDA_VISIBLE_DEVICES`。原脚本在模型启动前退出。现在严格解析本作业、本节点的单个设备；不扫描或抢用别人的卡。
2. **MIG 计算环境缺 Git。** 模型已经加载，但实验入口无法校验源码而退出。共享目录提供登录节点 Git 2.27 与必要非 glibc 库，并增加 Git 失败时提前退出的检查。CPU 推理线程和 prompt 线程均限制为申请到的 4 核。
3. **首轮审计误计入反思。** A 首轮 122 个审计事件，B 为 124 个；前 122 个逐条完全一致，B 多出的两项是首轮失败后的反思请求/响应。原代码仅按 `attempt=1` 过滤，误报首轮不一致。修复仅排除 `kind=reflection` 的首轮审计事件，反思调用仍计入成本；真实动作差异的拒绝测试保留。新增回归用例已先复现故障，再验证修复。

原始失败结果和日志保留，不并入正式筛选。到首次真实冒烟审计停止时，A/B 共 225 次模型调用、95.50 秒实验耗时；这部分属于调试成本。B 第三次尝试成功只能说明重试链路确实执行，不能从单题调试运行推出提示词优劣。

## 证据位置

学校仓库 `/hpc/home/aiaa4051_112/p3-work/repo` 下：

- `logs/priority-s1s4-20261123-submission/queue-diagnosis/`：队列/节点快照、替代队列尝试、MIG 分配检查、测试与审计差异证据。
- `logs/priority-s1s4-20261123-smoke-job-git-missing/`：已确认 `CUDA0: NVIDIA A30 MIG 2g.12gb (12032 MiB)`、驱动 580.178.04、固定 b12244 模型加载成功，但 Git 缺失的失败日志。
- 后续修复重跑继续使用作业号 30537；正式批次 30538–30557 必须等待冒烟成功，再统一迁移到相同 MIG 规格。

二期入口检查遇到 SSH 主机指纹与本机已保存记录不一致，连接在发送密码前停止。没有删除 known_hosts 或跳过身份校验；当前任务使用已验证可运行的一期 MIG 路径。
