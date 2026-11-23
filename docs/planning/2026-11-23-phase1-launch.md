# HPC Phase I launch implementation plan

Goal: 按用户最新授权，先在学校做快速 GPU 冒烟，通过后后台运行七组；关闭 SSH 不影响调度作业。

Design: 复用现有服务管理与七组循环，补充一期实际作业环境识别。新增明确标记的 smoke 模式，仅取 registry 前一题、4051、七组，保持提示词和每题预算不变；正式筛选仍为十题两种子。编译使用固定 b12244 源码、学校 CUDA/GCC，在 CPU 计算作业中进行。

- [x] 核对一期队列、作业环境变量、编译工具链；编译作业不申请 GPU。CPU 编译作业 30531 已启动，产物仍待完成验证。
- [x] `run_experiment.py --smoke` 仅缩小任务/种子范围；manifest/summary 明确 smoke，不计入正式筛选。测试其 7 单元、独立日志、full_two_seed_screening=false。
- [x] `run_school_gpu.sh` 支持实际 UniScheduler 作业标识和 CUDA 分配；记录 scheduler/job ID。保留未分配 GPU 时拒绝启动、失败清理和端口检查。30 项无模型测试通过。
- [ ] 测试适配，提交 GitHub 并同步学校干净版本；保留所有原指令和 baseline.json。
- [ ] 一张 GPU、15 分钟上限的冒烟；核对服务 GPU offload、真实动作/反思、首轮一致性、退出码及清理。
- [ ] 一张 GPU、最多 5 小时的正式 140 单元作业；可提前提交 `done(冒烟作业号)` 成功依赖，只有冒烟通过才执行。通过调度器后台运行，记录作业号和结果路径。

Acceptance: 不在本地运行模型；不在学校登录节点运行模型/重编译；同一冻结提交与参数；冒烟失败不启动正式筛选；向用户报告实际状态，不将排队称为运行或完成。
