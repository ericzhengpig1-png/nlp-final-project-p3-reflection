# C01-01 · 全量标注与预算依据

2026-11-23。仅分析历史数据，新增 GPU 用量为 0。返回[简短报告](C01-01-design.md)。

## 标注口径

覆盖 B 的全部10条反思，来自6道首轮失败任务；另外4题首轮成功，无反思。四条目标进展遗漏来自CD和盘子两题，不能算四个独立任务。这是单人首次标注，尚未独立复核。机器提取与人工判断分开保存在[分析数据](C01-01-analysis.json)。

事实以观察和实际反思请求为准；搜索未知位置的建议不自动算捏造。分别判断事实、可执行性、重置状态、后续行为和最终结果。没有发现明确“重置后仍持有上轮物品”的断言，重置提醒属于草案设计约束，尚非已确认根因。

10条均输出256 token、stop_type=limit，truncated均为false，且都进入下次 reset.memory。枕头、盘子、锅铲、CD各自两次反思逐字相同。盘子第二次的实际反馈已有冷却成功，反思仍未更新。

所有 L 行号指[原始 trace.jsonl](../../logs/m1-dev-ab-20261110/trace.jsonl)从1开始的物理行号；原始日志不修改。

## 逐条证据

### 放书 / 1 · 反思 L1874

任务：`json_2.1.1/valid_seen/pick_and_place_simple-Book-None-SideTable-329/trial_T20190908_050633_745514`；请求 L1872；下次终止 L1912（成功）。

> I was unable to find a book in the environment.

事实：未找到书属实；从已检查的抽屉拿书缺乏依据。 可执行性：具体动作有，但位置错误。 后续：重试从餐桌拿书成功，不能归功于抽屉建议。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L1762 / 1 / 2 | `open drawer 1` | You open the drawer 1. The drawer 1 is open. In it, you see a cellphone 1. |
| L1792 / 1 / 9 | `open drawer 2` | You open the drawer 2. The drawer 2 is open. In it, you see a creditcard 1. |
| L1804 / 1 / 12 | `go to drawer 3` | You arrive at drawer 3. On the drawer 3, you see a keychain 2. |
| L1816 / 1 / 16 | `go to drawer 4` | You arrive at drawer 4. On the drawer 4, you see a cd 2. |
| L1896 / 2 / 5 | `go to diningtable 1` | You arrive at diningtable 1. On the diningtable 1, you see a alarmclock 1, a book 3, a cd 3, a cd 1, a creditcard 2, a keychain 3, a keychain 1, a laptop 1, a mug 3, a mug 2, a mug 1, a pen 1, and a pencil 1. |
| L1902 / 2 / 6 | `take book 3 from diningtable 1` | You pick up the book 3 from the diningtable 1. |
| L1911 / 2 / 8 | `put book 3 in/on sidetable 1` | You move the book 3 to the sidetable 1. |

### 黄油刀 / 1 · 反思 L2034

任务：`json_2.1.1/valid_seen/pick_clean_then_place_in_recep-ButterKnife-None-CounterTop-8/trial_T20190909_105559_983897`；请求 L2032；下次终止 L2105（成功）。

> I was stuck in a loop in which I continually cleaned the sinkbasin 1 instead of cleaning the butterknife 1.

事实：把失败动作误述成清洗水槽；countertop 1 没有目标，2 已看到目标。 可执行性：拿取→清洁→放置顺序合理，位置不对。 后续：先从台面1拿取失败，再从台面2拿取、清洁、放置成功。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L1928 / 1 / 3 | `go to countertop 1` | You arrive at countertop 1. On the countertop 1, you see a cup 1, a houseplant 1, a lettuce 1, a soapbottle 1, a spatula 1, and a spoon 1. |
| L1940 / 1 / 5 | `clean butterknife 1 with sinkbasin 1` | Nothing happens. |
| L1973 / 1 / 14 | `go to countertop 2` | You arrive at countertop 2. On the countertop 2, you see a bread 1, a butterknife 1, a egg 1, a knife 2, a knife 1, a mug 3, a pen 1, a sink 1, a spatula 3, a spatula 2, and a spraybottle 2. |
| L2056 / 2 / 4 | `take butterknife 1 from countertop 1` | Nothing happens. |
| L2086 / 2 / 10 | `take butterknife 1 from countertop 2` | You pick up the butterknife 1 from the countertop 2. |
| L2095 / 2 / 12 | `clean butterknife 1 with sinkbasin 1` | You clean the butterknife 1 using the sinkbasin 1. |
| L2104 / 2 / 14 | `put butterknife 1 in/on countertop 2` | You move the butterknife 1 to the countertop 2. |

### 枕头 / 1 · 反思 L2212

任务：`json_2.1.1/valid_seen/look_at_obj_in_light-Pillow-None-DeskLamp-323/trial_T20190908_053153_077977`；请求 L2210；下次终止 L2310（失败）。

> I was unable to examine the pillow with the desklamp because the pillow was not found on the sidetable 1 or sidetable 2.

事实：未找到枕头属实；建议重查已检查的 desk 1 / drawer 1。 可执行性：没有有依据的新路径；搜索未知位置本身不算捏造。 后续：下次前25个环境动作重复，然后无效拿取枕头，失败。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L2169 / 1 / 21 | `open drawer 1` | You open the drawer 1. The drawer 1 is open. In it, you see nothing. |
| L2172 / 1 / 22 | `go to desk 1` | You arrive at desk 1. On the desk 1, you see a bowl 1, a cellphone 1, a desklamp 1, a keychain 2, a mug 2, a mug 1, and a pencil 1. |
| L2175 / 1 / 23 | `go to sidetable 1` | You arrive at sidetable 1. On the sidetable 1, you see a cellphone 2. |
| L2178 / 1 / 24 | `go to sidetable 2` | You arrive at sidetable 2. On the sidetable 2, you see a creditcard 2, a desklamp 2, a keychain 3, and a pen 1. |
| L2288 / 2 / 25 | `use desklamp 2` | You turn on the desklamp 2. |
| L2294 / 2 / 26 | `take pillow 1 from sidetable 2` | Nothing happens. |

### 枕头 / 2 · 反思 L2313

任务：`json_2.1.1/valid_seen/look_at_obj_in_light-Pillow-None-DeskLamp-323/trial_T20190908_053153_077977`；请求 L2311；下次终止 L2408（失败）。

> I was unable to examine the pillow with the desklamp because the pillow was not found on the sidetable 1 or sidetable 2.

事实：与上一条逐字一致，没利用新发生的无效拿取反馈。 可执行性：仍无有依据的新路径。 后续：第三次仍重复前25个动作，未拿枕头，失败。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L2276 / 2 / 21 | `open drawer 1` | You open the drawer 1. The drawer 1 is open. In it, you see nothing. |
| L2279 / 2 / 22 | `go to desk 1` | You arrive at desk 1. On the desk 1, you see a bowl 1, a cellphone 1, a desklamp 1, a keychain 2, a mug 2, a mug 1, and a pencil 1. |
| L2294 / 2 / 26 | `take pillow 1 from sidetable 2` | Nothing happens. |
| L2389 / 3 / 25 | `use desklamp 2` | You turn on the desklamp 2. |
| L2395 / 3 / 26 | `use desklamp 2` | You turn on the desklamp 2. |
| L2407 / 3 / 30 | `go to drawer 4` | You arrive at drawer 4. The drawer 4 is open. In it, you see nothing. |

### 盘子 / 1 · 反思 L2585

任务：`json_2.1.1/valid_seen/pick_cool_then_place_in_recep-Plate-None-Cabinet-7/trial_T20190907_231206_512424`；请求 L2583；下次终止 L2677（失败）。

> I was unable to find a plate to cool.

事实：称未找到盘子，但第3动作已在餐桌看到 plate 3。 可执行性：给出餐桌位置，也提出未经本轨迹支持的 stoveburner 冷却。 后续：重试从餐桌拿盘子，用 fridge 冷却，未完成放置，失败。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L2500 / 1 / 3 | `go to diningtable 1` | You arrive at diningtable 1. On the diningtable 1, you see a book 2, a book 1, a bowl 2, a butterknife 1, a fork 2, a fork 1, a houseplant 1, a lettuce 2, a lettuce 1, a plate 3, a spoon 1, a statue 1, a tomato 2, and a tomato 1. |
| L2589 / 2 / 1 | `go to diningtable 1` | You arrive at diningtable 1. On the diningtable 1, you see a book 2, a book 1, a bowl 2, a butterknife 1, a fork 2, a fork 1, a houseplant 1, a lettuce 2, a lettuce 1, a plate 3, a spoon 1, a statue 1, a tomato 2, and a tomato 1. |
| L2592 / 2 / 2 | `take plate 3 from diningtable 1` | You pick up the plate 3 from the diningtable 1. |
| L2598 / 2 / 4 | `cool plate 3 with fridge 1` | You cool the plate 3 using the fridge 1. |
| L2604 / 2 / 6 | `open cabinet 1` | You open the cabinet 1. The cabinet 1 is open. In it, you see nothing. |
| L2676 / 2 / 30 | `open cabinet 13` | You open the cabinet 13. The cabinet 13 is open. In it, you see a saltshaker 3. |

### 盘子 / 2 · 反思 L2680

任务：`json_2.1.1/valid_seen/pick_cool_then_place_in_recep-Plate-None-Cabinet-7/trial_T20190907_231206_512424`；请求 L2678；下次终止 L2772（失败）。

> I was unable to find a plate to cool.

事实：称未找到盘子，但已经拿到并冷却；反思请求含冷却反馈。 可执行性：沿用上一条，漏掉完成的子目标。 后续：第三次看到盘子却未拿取/冷却，最终失败；不据此断言因果。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L2592 / 2 / 2 | `take plate 3 from diningtable 1` | You pick up the plate 3 from the diningtable 1. |
| L2598 / 2 / 4 | `cool plate 3 with fridge 1` | You cool the plate 3 using the fridge 1. |
| L2604 / 2 / 6 | `open cabinet 1` | You open the cabinet 1. The cabinet 1 is open. In it, you see nothing. |
| L2676 / 2 / 30 | `open cabinet 13` | You open the cabinet 13. The cabinet 13 is open. In it, you see a saltshaker 3. |
| L2690 / 3 / 3 | `go to diningtable 1` | You arrive at diningtable 1. On the diningtable 1, you see a book 2, a book 1, a bowl 2, a butterknife 1, a fork 2, a fork 1, a houseplant 1, a lettuce 2, a lettuce 1, a plate 3, a spoon 1, a statue 1, a tomato 2, and a tomato 1. |
| L2699 / 3 / 6 | `go to diningtable 1` | You arrive at diningtable 1. On the diningtable 1, you see a book 2, a book 1, a bowl 2, a butterknife 1, a fork 2, a fork 1, a houseplant 1, a lettuce 2, a lettuce 1, a plate 3, a spoon 1, a statue 1, a tomato 2, and a tomato 1. |
| L2771 / 3 / 30 | `open cabinet 12` | You open the cabinet 12. The cabinet 12 is open. In it, you see nothing. |

### 两把锅铲 / 1 · 反思 L2905

任务：`json_2.1.1/valid_seen/pick_two_obj_and_place-Spatula-None-Drawer-13/trial_T20190908_183331_203888`；请求 L2903；下次终止 L3012（失败）。

> I was unable to put two spatulas in the drawer because I was unable to find a spatula.

事实：没找到 spatula 属实，没有直接事实矛盾。 可执行性：先找再放方向合理但泛泛，未分解两个物品的完成条件。 后续：重试转查柜子，拿到的是 dishsponge，失败。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L2874 / 1 / 21 | `put spatula 1 in/on drawer 12` | Nothing happens. |
| L2898 / 1 / 29 | `go to drawer 20` | Nothing happens. |
| L2981 / 2 / 22 | `open cabinet 12` | You open the cabinet 12. The cabinet 12 is open. In it, you see a dishsponge 1. |
| L3005 / 2 / 29 | `take dishsponge 1 from cabinet 12` | You pick up the dishsponge 1 from the cabinet 12. |
| L3011 / 2 / 30 | `go to cabinet 12` | Nothing happens. |

### 两把锅铲 / 2 · 反思 L3015

任务：`json_2.1.1/valid_seen/pick_two_obj_and_place-Spatula-None-Drawer-13/trial_T20190908_183331_203888`；请求 L3013；下次终止 L3107（失败）。

> I was unable to put two spatulas in the drawer because I was unable to find a spatula.

事实：同样未找到目标；文本与上一条相同，未提拿错物品。 可执行性：泛泛的找和放，未分解两把目标。 后续：第三次拿到并放入一把 spatula，整体任务仍失败。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L2981 / 2 / 22 | `open cabinet 12` | You open the cabinet 12. The cabinet 12 is open. In it, you see a dishsponge 1. |
| L3005 / 2 / 29 | `take dishsponge 1 from cabinet 12` | You pick up the dishsponge 1 from the cabinet 12. |
| L3079 / 3 / 21 | `go to countertop 1` | You arrive at countertop 1. On the countertop 1, you see a bread 1, a butterknife 1, a fork 1, a lettuce 3, a lettuce 1, a pencil 1, a peppershaker 1, a plate 1, a spatula 1, a spoon 3, and a winebottle 1. |
| L3082 / 3 / 22 | `take spatula 1 from countertop 1` | You pick up the spatula 1 from the countertop 1. |
| L3088 / 3 / 24 | `put spatula 1 in/on drawer 1` | You move the spatula 1 to the drawer 1. |
| L3106 / 3 / 30 | `go to drawer 7` | You arrive at drawer 7. The drawer 7 is open. In it, you see nothing. |

### CD / 1 · 反思 L3208

任务：`json_2.1.1/valid_seen/look_at_obj_in_light-CD-None-DeskLamp-314/trial_T20190907_114323_767231`；请求 L3206；下次终止 L3306（失败）。

> I was unable to find a cd in the environment.

事实：称未找到 CD，但第11动作已拾取、第17动作已看到台灯。 可执行性：继续搜索和无关物品枚举，未针对剩余目标。 后续：第二次重拿CD，看到台灯后离开；后来 use 得到 Nothing happens，失败。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L3138 / 1 / 10 | `open drawer 5` | You open the drawer 5. The drawer 5 is open. In it, you see a cd 3, and a cd 2. |
| L3144 / 1 / 11 | `take cd 3 from drawer 5` | You pick up the cd 3 from the drawer 5. |
| L3162 / 1 / 17 | `go to desk 1` | You arrive at desk 1. On the desk 1, you see a alarmclock 1, a book 1, a desklamp 1, a keychain 1, and a pencil 3. |
| L3245 / 2 / 11 | `take cd 3 from drawer 5` | You pick up the cd 3 from the drawer 5. |
| L3248 / 2 / 12 | `go to desk 1` | You arrive at desk 1. On the desk 1, you see a alarmclock 1, a book 1, a desklamp 1, a keychain 1, and a pencil 3. |
| L3281 / 2 / 23 | `go to dresser 1` | You arrive at dresser 1. On the dresser 1, you see a pen 2, and a pencil 2. |
| L3296 / 2 / 28 | `use desklamp 1` | Nothing happens. |

### CD / 2 · 反思 L3309

任务：`json_2.1.1/valid_seen/look_at_obj_in_light-CD-None-DeskLamp-314/trial_T20190907_114323_767231`；请求 L3307；下次终止 L3404（失败）。

> I was unable to find a cd in the environment.

事实：再次称未找到，和实际拾取矛盾；文本与上一条相同。 可执行性：未根据新的失败反馈更新。 后续：第三次看到CD未拿取，也未 use 台灯，失败；不能证明唯一原因。

| 行号 / 尝试 / 动作 | 行动 | 环境反馈 |
| --- | --- | --- |
| L3245 / 2 / 11 | `take cd 3 from drawer 5` | You pick up the cd 3 from the drawer 5. |
| L3248 / 2 / 12 | `go to desk 1` | You arrive at desk 1. On the desk 1, you see a alarmclock 1, a book 1, a desklamp 1, a keychain 1, and a pencil 3. |
| L3296 / 2 / 28 | `use desklamp 1` | Nothing happens. |
| L3340 / 3 / 10 | `open drawer 5` | You open the drawer 5. The drawer 5 is open. In it, you see a cd 3, and a cd 2. |
| L3343 / 3 / 11 | `go to desk 1` | You arrive at desk 1. On the desk 1, you see a alarmclock 1, a book 1, a desklamp 1, a keychain 1, and a pencil 3. |
| L3400 / 3 / 29 | `go to desk 1` | You arrive at desk 1. On the desk 1, you see a alarmclock 1, a book 1, a desklamp 1, a keychain 1, and a pencil 3. |
| L3403 / 3 / 30 | `go to sidetable 1` | Nothing happens. |

## 草案的唯一修改

[C01 v1](../../prompts/c01_observation_v1.draft.txt)只保存反思指令段：原 B 指令全文后增加一段，具体如下。接入时保留原 `Here are two examples:`、两个反思示例、当前失败轨迹、原 memory 段及 `New plan:` 尾部，内容与顺序不变。文件不是可直接发送的完整请求，也尚未接入 runner。

> Support your diagnosis with a brief quote from the observed feedback. Distinguish confirmed progress from unknown object locations or action outcomes; the history describes a past attempt, so after reset, re-establish any required state rather than assuming it persists.

没有写入 CD/盘子答案、改变动作提示、添加 C02 单动作要求或提高256 token上限。额外引用可能占用输出预算，小模型也可能误引；未测 tokenizer，不报精确新增 token 数。候选尚未冻结或测试。接入时需验证完整请求仅增加这一段。

## 预算依据

历史记录为 RTX 5060 Laptop GPU / Vulkan + WSL；学校设备、计费口径、累计用量与余额待核。以下为单GPU串行情景估算，不是费用报价。

| 既有实测 | 调用 | 输入 token | 输出 token | 后端推理秒 | 请求墙钟秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A_action | 566 | 1,127,604 | 5,956 | 190.789 | 193.757 |
| B_action | 537 | 1,178,475 | 5,679 | 198.443 | 201.994 |
| B_reflection | 10 | 26,781 | 2,560 | 24.990 | 25.668 |

合计40次尝试，端到端590.928秒；请求421.420秒，差额169.508秒，摊为每次尝试4.238秒。这是估算摊销，不是逐次环境实测；服务启动、下载、排队及占卡空闲不含在该运行时长中。

普通情景假设C成本与B相近：两题试跑=2×B的CD与放书请求秒+10×4.238；十题B/C=2×B请求秒+40×4.238；30题A/B/C=3×(A请求秒+2×B请求秒)+180×4.238。

满工作量情景：每题3×49=147次动作模型请求，B/C最多另2次反思；30个环境动作不等于30次模型请求。动作请求P95=0.5152秒，反思P95=2.6204秒，排序后取floor(0.95×(n−1))位置。B/C每题=147×动作P95+2×反思P95+3×摊销；A去掉反思。这个情景不是严格时间上界，长输出/新设备/超时可能更慢。

| 阶段（仅C01 v1） | 普通 / 满工作量情景 | 请求数上限 | 待审批卡时上限建议 |
| --- | ---: | ---: | ---: |
| 两题 B/C 试跑 | 2.6 / 6.2 分钟 | 596 | 0.5 GPU小时 |
| 十题 B/C 开发 | 10.4 / 31.2 分钟 | 2,980 | 1.0 GPU小时 |
| 十题 B/C 换种子复核 | 10.4 / 31.2 分钟 | 2,980 | 1.0 GPU小时 |
| 30题 A/B/C 正式 | 45.2 / 137.9 分钟 | 13,350 | 3.0 GPU小时 |

情景不是置信区间；两者均不含下载、部署、加载和占卡空闲。卡时建议基于相近有效吞吐并留准备余量，合计5.5卡时，覆盖一个候选和一次复核，不含第二版或技术重跑，也没有实际预留或批准。若有效运行整体慢3倍，满工作量情景分别约18.7、93.7、93.7、413.7分钟，原建议可能不足。

推荐只先批0.5卡时做环境准备完成后的两题B/C试跑，记录GPU分配起止、加载和运行速度，再重算开发/复核/正式预算。两题仅验接入与计量；达到上限停止新增派发，保留未完成状态，不自动扩额。当前用户批准GPU预算为0。

## 证据版本

运行 `m1-dev-ab-20261110`；原提交 `9b3ca7b6328d817e3e22abdd761a209dcb333ea7`。预算复算数字与逐条摘录见[分析数据](C01-01-analysis.json)。

| 文件 | SHA256 |
| --- | --- |
| `logs/m1-dev-ab-20261110/trace.jsonl` | `5785a47257783ebaab2106b8323a4cad03d6bb476b6acb2be70ccbd0f9bb2235` |
| `logs/m1-dev-ab-20261110/summary.json` | `715df17bbb1dda3450ec1af3a4f41af7c8f4352dce3a0971d22e7abfa93aa5ba` |
| `logs/m1-dev-ab-20261110/manifest.json` | `0323d88d3f73d2891c6e6e8e7f7141bba9889e1d24d4160f048de098e9ebb695` |
| `configs/baseline.json` | `5edb6c26f616cec8a76586ced9a9b0681375101f86582de9bac619f1c251ef44` |
| `scripts/run_baseline.py` | `e528883757f61f56f440208865ad2106820704f89639e945ac6e5d94712ee024` |
| `src/agent/llama_server.py` | `000237f624d7d95dc789369ec33800f943c24eca0e4df8179056a3ea097248ed` |
| `data/reflexion/generate_reflections.py` | `d7fbe4af7ff21ce9bc73ad2bcf16bf265682d1fb3554dc62985f3ada09997ef7` |
| `prompts/c01_observation_v1.draft.txt` | `b54ce1ac0ee59bc11d482575cd706f8117a9f62bc7bb074f29f69289da70f54d` |
