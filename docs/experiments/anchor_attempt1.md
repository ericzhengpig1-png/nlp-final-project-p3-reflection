# Anchor 尝试 1

这是 P3 的独立小规模移植实验。实现位于本地实验分支 `exp/anchor-attempt-1`。A/B 对照引用 M1 的 `m1-dev-ab-20261110`。两个 Anchor 条件共用同一动作策略，只比较同一批候选笔记经过筛选与全部保留。课程 C 组继续使用「只改原始反思提示词」的定义。

## 运行

沿用 [M1 环境和模型](baseline.md)。在仓库根目录执行下列命令。新环境使用自己的 Python 路径、已下载的 ALFWorld 压缩包和唯一的运行编号。

```bash
../.p3-venv/bin/python scripts/run_anchor.py probe --run-id anchor-attempt1-probe
../.p3-venv/bin/python scripts/run_anchor.py build --run-id anchor-attempt1-bank-v1 --archive ../p3-assets/json_2.1.2_tw-pddl.zip
../.p3-venv/bin/python scripts/run_anchor.py pilot --run-id anchor-attempt1-pilot --bank logs/anchor-attempt1-bank-v1/bank.json
../.p3-venv/bin/python scripts/run_anchor.py dev --run-id anchor-attempt1-dev --bank logs/anchor-attempt1-bank-v1/bank.json
```

先核对 `pilot` 日志中的复位、动作上限、相同库哈希和实际检索，再执行 `dev`。训练 ID 在 [配置](../../configs/anchor_attempt1.json) 中预先固定。从官方 `train` 数据按任务类型分组，排除不可解、可移动容器和切片题，每类选 `SHA-256("anchor-attempt-1:4051:" + task_id)` 最小的一个。开发集沿用 10 道，留出集仅登记 ID。

## 筛选和移植范围

- 每道训练题分别保存模型轨迹和官方训练 walkthrough 的实际环境轨迹。模型选择决策点、写提示并选择可行命令。环境反馈提供正例的任务物品或成功证据，以及负例的重复或无效果证据。失败纠正提示必须提供不同动作类别的替代。官方示范用于补充模型未产生的正例。
- 保存动作前的任务、示例、历史、观察、已有笔记和有序合法命令。两份回放只相差一条待测提示。使用 llama.cpp 的原始首 token 对数概率，合并共用首 token 的命令，再对固定类别归一化。缺失分数时记录探测无效。该方法使用本地模型的真实分数。
- 按论文第 4 节和附录 C.4/D.2 计算以 bit 为单位的 JS 散度。成功笔记要求 JS ≥ 0.05、原动作类别为首选、概率增加 ≥ 0.04。失败笔记要求 JS ≥ 0.12，再满足原类别概率下降 ≥ 0.10 或注入后的首选改为其他类别。后一分支是论文的排名规则。
- 两库引用同一批候选提示的原文。评测以任务类型和可行的动作类别限定检索，按观察与提示线索的词汇重合度排序，最多注入三条。评测前后核对笔记库哈希。移植使用共享的离线训练轨迹、简化检索和 A/B 的模型、预算及解码参数。论文的在线维护、置信度和跨类型检索未纳入本次实验。
- Anchor 的动作提示列出合法命令，并用受约束的解码选一条，同时保留一个同类 Reflexion 示例。A/B 使用原来的自由输出提示，因此筛选的独立对照是两个 Anchor 组。每题最多三次，每次最多 30 个环境动作，成功立即停止。

原文 [Anchor 第 4 节与附录 C–E](https://arxiv.org/html/2611.10382v1)。

## 已核对的笔记库和试跑

最终建库运行 `anchor-attempt1-bank-v1`。六条模型轨迹均在 30 动作内失败，六条官方训练示范均由环境判为成功。两者共生成 30 条有效候选，其中 12 条是好动作保留，18 条是失败纠正。30 对首 token 分数齐全。保留的 9 条都是失败纠正，而且原动作类别的概率均下降至少 0.10。最终建库用 107.14 秒，配对筛选另用 13.94 秒。

`anchor-attempt-1-02-1-01` 来自放置肥皂瓶训练题。原动作是反复打开柜子 2。加笔记后，`open` 类首 token 的概率从 0.49532 降到 0.02594，JS 为 0.35947 bit。两题试跑时，两个 Anchor 组都把这条笔记放进了放书任务的第一个提示，筛选版随后输出 `go to drawer 3`。该尝试最终失败。核对以 `screening` 和 `decision` 事件为准。

两题试跑两组均为 0/2，合计 179.17 秒。实际检索、初始状态哈希、预算和库哈希均通过核对。原始试跑前的训练诊断单独保存在证据包，最终评测统一引用冻结库。

## 完整十题结果

每格为首次成功的尝试编号与 GPU 后端推理秒数。× 表示三次均失败。

| 任务 ID 类型与物品 | A（M1） | B（M1） | 筛选 | 不筛选 |
| --- | ---: | ---: | ---: | ---: |
| pick_and_place_simple-Book-None-SideTable-329 | × / 38.57 | 2 / 19.22 | × / 23.08 | × / 22.76 |
| pick_clean_then_place_in_recep-ButterKnife-None-CounterTop-8 | × / 48.65 | 2 / 32.87 | × / 35.73 | × / 35.80 |
| look_at_obj_in_light-Pillow-None-DeskLamp-323 | × / 27.46 | × / 37.43 | × / 23.73 | × / 27.69 |
| pick_and_place_simple-Knife-None-SideTable-3 | 1 / 2.55 | 1 / 2.50 | × / 23.51 | × / 24.97 |
| pick_clean_then_place_in_recep-SoapBar-None-Toilet-428 | 1 / 6.84 | 1 / 6.90 | × / 29.52 | × / 29.13 |
| pick_cool_then_place_in_recep-Plate-None-Cabinet-7 | 2 / 15.61 | × / 39.70 | × / 27.09 | × / 28.59 |
| pick_heat_then_place_in_recep-Mug-None-Cabinet-26 | 1 / 5.78 | 1 / 4.42 | × / 30.31 | × / 26.73 |
| pick_two_obj_and_place-Spatula-None-Drawer-13 | × / 28.26 | × / 41.29 | × / 28.77 | × / 31.10 |
| look_at_obj_in_light-CD-None-DeskLamp-314 | 2 / 14.44 | × / 36.58 | × / 25.62 | × / 25.30 |
| pick_and_place_simple-Candle-None-Toilet-429 | 1 / 2.63 | 1 / 2.53 | × / 26.92 | × / 24.40 |

| 条件 | 成功数 | 模型调用 | GPU 后端秒数 | 端到端秒数 |
| --- | ---: | ---: | ---: | ---: |
| A（M1） | 6/10 | 566 | 190.79 | 合并计时 |
| B（M1） | 6/10 | 547 | 223.43 | 合并计时 |
| 筛选 | 0/10 | 900 | 274.26 | 415.58 |
| 不筛选 | 0/10 | 900 | 276.47 | 417.47 |

历史 A/B 联合耗时 590.93 秒。本次两个 Anchor 组联合耗时 833.07 秒。
端到端时间包含环境与服务开销。推理时间为 llama.cpp 记录的提示处理和解码耗时之和。

筛选版 900 个环境动作，其中 0 个拿取命令。 523/900 个决策注入了笔记。 30 次尝试达到动作上限。

不筛选版 900 个环境动作，其中 0 个拿取命令。 900/900 个决策注入了笔记。 30 次尝试达到动作上限。

候选动作首词的偏好变化可以在训练决策上被实测。开发集的任务完成情况另见上表。相同任务类型的检索有时会召回另一物体的训练提示，例如放书检索到肥皂瓶提示。
