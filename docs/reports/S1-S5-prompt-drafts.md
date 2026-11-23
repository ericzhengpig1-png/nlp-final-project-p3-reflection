# S1–S5 完整提示词、原版对照与案例推演

2026-11-23｜版本：五个独立 v1 草案｜未接入运行器、未调用模型、未运行实验｜新增 GPU 用量 **0**。

## 阅读与使用范围

本页完整列出五份英文反思指令及其原版对照，不需要读者自行把调研片段拼回原文。每份文本也单独保存在 [prompts/reflection_candidates/](../../prompts/reflection_candidates/)。本页是设计交付，未选择实验方案或增加实验次数。

这里的“完整指令”指替换 B 请求开头的完整固定指令段。完整模型请求还包含原来的两份示例、当次失败轨迹、已有反思和结尾；拼装边界见本文最后一节。它们都按原机制保留，不能仅把一个指令文件单独发给模型当作完整轨迹请求。

案例的英文输出都是**人工撰写的期望示意，不是本项目模型生成的结果，也不是新增 few-shot**。只说明要观察怎样的改变，不能证明模型会生成、actor 会采用，或成功率会上升。不同方向可能产生相似的正确计划，比较重点在各自约束是否起效。

## B 原版与共同改动方式

原版来自 [generate_reflections.py](../../data/reflexion/generate_reflections.py) 的 `_generate_reflection_query`，原样摘出从开头到 `Give your plan after "Plan".` 的固定指令，保存为 [b_original_instruction.txt](../../prompts/reflection_candidates/b_original_instruction.txt)。

```text
You will be given the history of a past experience in which you were placed in an environment and given a task to complete. You were unsuccessful in completing the task. Do not summarize your environment, but rather think about the strategy and path you took to attempt to complete the task. Devise a concise, new plan of action that accounts for your mistake with reference to specific actions that you should have taken. For example, if you tried A and B but forgot C, then devise a plan to achieve C with environment-specific actions. You will need this later when you are solving the same task. Give your plan after "Plan".
```

五版均保留上述原文，只在其后、`Here are two examples:` 之前增加一段本方向的要求。没有删除或替换原句，也没有把其余四个方向一起叠加进去。具体约束存在内容上的交集，因此这是一组按主要目的区分的候选，不声称它们在机制上完全正交。

| 版本 | 主要变化 | 完整指令文件 | 英文空白分词数：总数 / 新增 |
| --- | --- | --- | --- |
| B | 原版参照 | [原版](../../prompts/reflection_candidates/b_original_instruction.txt) | 112 / 0 |
| S1 | 观察证据约束 | [s1_observation_v1.draft.txt](../../prompts/reflection_candidates/s1_observation_v1.draft.txt) | 182 / 70 |
| S2 | 失败步骤与前置条件 | [s2_diagnosis_v1.draft.txt](../../prompts/reflection_candidates/s2_diagnosis_v1.draft.txt) | 185 / 73 |
| S3 | 新证据修订旧建议 | [s3_update_v1.draft.txt](../../prompts/reflection_candidates/s3_update_v1.draft.txt) | 190 / 78 |
| S4 | 剩余目标与重试路径 | [s4_remaining_goals_v1.draft.txt](../../prompts/reflection_candidates/s4_remaining_goals_v1.draft.txt) | 193 / 81 |
| S5 | 去重与信息密度 | [s5_density_v1.draft.txt](../../prompts/reflection_candidates/s5_density_v1.draft.txt) | 169 / 57 |

词数仅用于看输入长度变化，不是 Qwen tokenizer 的 token 数。五版继续使用原输出上限 256 token；新增输入可能增加成本，尚未测量。原 [C01 v1 草案](../../prompts/c01_observation_v1.draft.txt)保留，本组 S1 是新的独立比较草案，不覆盖旧文本。

## 两个案例：严格限定反思时可见的信息

原始证据：[trace.jsonl](../../logs/m1-dev-ab-20261110/trace.jsonl)，下列 L 均为从 1 开始的物理行号；原十条标注见[证据附件](C01-01-evidence.md)。

| 项目 | 盘子：第二次失败后、第三次尝试前 | 两把锅铲：第二次失败后、第三次尝试前 |
| --- | --- | --- |
| 任务原文 | `cool some plate and put it in cabinet.` | `put two spatula in drawer.` |
| 实际反思请求 / 输出 | L2678 / L2680 | L3013 / L3015 |
| 已有进展 | 餐桌看到盘子 L2589；拿到 plate 3 L2592；fridge 冷却成功 L2598；打开 cabinet 1 L2604 | L2981 看到 dishsponge；L3005 拿到 dishsponge；没有确认拿到或放好锅铲 |
| 实际障碍 | 打开 cabinet 1 后继续逐个搜索至 cabinet 13；没有执行 put，L2677 动作到限失败 | 拿取前两次尝试放置 dishsponge 均无效 L2984、2996；随后拿错物体，L3012 动作到限失败 |
| 原版反思问题 | 仍说没找到盘子，建议 stoveburner 冷却；大量重复，且与 L2585 完全相同 | “没找到锅铲”仍属实，但计划没有落实第二把；重复同一放置承诺，并与 L2905 完全相同 |
| 不能提前使用的信息 | 第三轮的新行动和反馈 | 第三轮 L3079 才看到锅铲，L3082 拿取、L3088 放入一把；这些只能用于事后解释 |

盘子不能写成“put 动作失败”，因为第二轮没有 put；锅铲不能写成“现在只差第二把”，因为生成第二次反思时还没有放好第一把。

## S1 · 观察证据约束

**完整英文指令：**[单独文本](../../prompts/reflection_candidates/s1_observation_v1.draft.txt)。

```text
You will be given the history of a past experience in which you were placed in an environment and given a task to complete. You were unsuccessful in completing the task. Do not summarize your environment, but rather think about the strategy and path you took to attempt to complete the task. Devise a concise, new plan of action that accounts for your mistake with reference to specific actions that you should have taken. For example, if you tried A and B but forgot C, then devise a plan to achieve C with environment-specific actions. You will need this later when you are solving the same task. Give your plan after "Plan".

Check factual claims against feedback from the latest attempt. Distinguish seeing an object, taking it, and successfully changing its state. Support the key factual claim behind your correction with one short excerpt from that attempt. A planned action or an earlier reflection is not evidence that an action succeeded. If the feedback is insufficient, state what remains unknown. Use these facts to correct the retry plan without retelling the environment.
```

**相对 B 改了什么：**原版只笼统要求从失败经历制定计划。S1 新增事实核验：明确区分看见、拿到、处理成功；用最新尝试的一段短反馈支持关键判断；计划和旧反思不能充当成功证据；不足以判断时写未知。

**盘子：原问题 → 期望改善。**原反思 L2680 说没找到盘子，但 L2598 已确认冷却。S1 的直接目标是纠正这项事实，并让后续计划使用已经观察到的物体和工具信息。重试仍从重置后的状态开始。

```text
Plan: Feedback says, "You cool the plate 3 using the fridge 1." I had taken and cooled the plate in the last attempt, but there was no confirmed placement in a cabinet. After reset, take plate 3 from diningtable 1 again, cool it with fridge 1, then go to cabinet 1, open it if needed, and put the plate inside.
```

**锅铲：原问题 → 期望改善。**原反思“没有找到锅铲”在第二轮结束时仍符合轨迹，不能为了展示改进而把它改成“已经找到”。可以补充的事实是：实际拿到的是 dishsponge，锅铲位置仍未知。

```text
Plan: Feedback says, "You pick up the dishsponge 1 from the cabinet 12." This confirms picking up a dishsponge, not a spatula. No spatula pickup or placement was confirmed, and the spatula locations are unknown. On retry, search for objects identified as spatulas and complete the required placements of two different spatulas.
```

**能支持到哪里：**盘子案例应首先看事实矛盾是否消失；锅铲案例应看是否正确区分目标物与错误物体。S1 不提供新的物体位置，也不保证 actor 会完成最后一步。

## S2 · 失败步骤与前置条件

**完整英文指令：**[单独文本](../../prompts/reflection_candidates/s2_diagnosis_v1.draft.txt)。

```text
You will be given the history of a past experience in which you were placed in an environment and given a task to complete. You were unsuccessful in completing the task. Do not summarize your environment, but rather think about the strategy and path you took to attempt to complete the task. Devise a concise, new plan of action that accounts for your mistake with reference to specific actions that you should have taken. For example, if you tried A and B but forgot C, then devise a plan to achieve C with environment-specific actions. You will need this later when you are solving the same task. Give your plan after "Plan".

Identify the main failed action or omitted required step and its observed outcome. Check which prerequisite was missing or unconfirmed at that point, using the history rather than assuming a cause. Separate what the feedback establishes from a possible explanation. If the cause cannot be determined, say so. Give the concrete correction needed before retrying that step; if the step was never attempted, explain what must be done to reach and complete it.
```

**相对 B 改了什么：**原版要求“考虑自己的错误”，没有规定怎样定位错误。S2 新增“失败动作或遗漏步骤 → 当时前置条件 → 具体修正”，并要求把观察事实与可能原因分开。相比调研片段，明确加入未执行步骤，避免把盘子的漏放置误写成一次放置失败。

**盘子：原问题 → 期望改善。**盘子第二轮没有尝试 put，因此不能虚构“放置命令失败”。可确认的问题是：拿取、冷却和打开 cabinet 1 后，继续搜索柜子，没有执行最终放置。

```text
Plan: The required placement step was never attempted. After taking and cooling the plate, I opened cabinet 1 but kept searching other cabinets until the action limit. On retry, repeat taking and cooling, go to cabinet 1, open it if needed, and put the plate inside before continuing any search.
```

**锅铲：原问题 → 期望改善。**L2984、2996 的放置都发生在成功拿取 L3005 之前，且所操作的是 dishsponge。可以核验“没有拿取成功”和“物体不匹配”两个问题；不能由 Nothing happens. 单独断言唯一失败原因。

```text
Plan: I attempted to put dishsponge 1 before any successful pickup, and that object did not match the requested spatula. Those attempts did not establish progress toward the goal. After reset, search for a spatula, confirm taking it before placing it in an open drawer, then repeat with a different spatula. Their locations remain unknown.
```

**能支持到哪里：**S2 应让诊断落到可检查的步骤和条件。它仍可能遗漏其他原因，或把推测说得过于确定；评价时需检查理由，不只检查文字是否像一段合理解释。

## S3 · 新证据修订旧建议

**完整英文指令：**[单独文本](../../prompts/reflection_candidates/s3_update_v1.draft.txt)。

```text
You will be given the history of a past experience in which you were placed in an environment and given a task to complete. You were unsuccessful in completing the task. Do not summarize your environment, but rather think about the strategy and path you took to attempt to complete the task. Devise a concise, new plan of action that accounts for your mistake with reference to specific actions that you should have taken. For example, if you tried A and B but forgot C, then devise a plan to achieve C with environment-specific actions. You will need this later when you are solving the same task. Give your plan after "Plan".

When past plans are provided, compare their advice with the latest attempt. Keep advice that remains supported, explicitly correct advice contradicted by new feedback, and add only newly needed guidance. Identify the relevant new evidence behind any revision. If no relevant evidence changed, do not invent a change. Make the revised retry plan self-contained so that it clearly supersedes any mistaken earlier advice. If no past plan is provided, write the initial retry plan from the failed attempt.
```

**相对 B 改了什么：**原请求虽然已经附带旧计划，却没有显式要求比较和修订。S3 新增保留、纠正、增补规则和修订依据；要求新计划可独立理解。无旧计划时正常写第一次反思；没有相关新证据时允许保留旧建议。

**盘子：原问题 → 期望改善。**旧计划称没找到盘子并建议用 stoveburner 冷却；最新反馈已经证明拿取成功且 fridge 冷却有效。应明确替换失效的判断和工具建议，把漏放置纳入新计划。

```text
Plan: My earlier claim that I had not found a plate was contradicted by this attempt. Taking plate 3 from diningtable 1 and cooling it with fridge 1 succeeded, so the earlier stoveburner advice should be replaced. After reset, repeat those successful steps, then go to cabinet 1, open it if needed, and put the plate inside instead of searching every cabinet.
```

**锅铲：原问题 → 期望改善。**“仍需寻找锅铲”没有被新证据推翻，应保留；第二轮新增的错误是操作了 dishsponge。有效更新应补上目标物核对，而不是硬把尚未找到改写为已经找到。

```text
Plan: The earlier advice to find spatulas is still needed. The latest attempt revealed an additional mistake: I tried to place and then took dishsponge 1, which is not the target object. On retry, take only objects identified as spatulas, place the first in a drawer, and repeat with a different second spatula. Their locations are still unknown.
```

**能支持到哪里：**修订文字不会删除原记忆；旧错误仍在上下文中，actor 可能继续受其影响。本方向主要作用于第二次反思及随后的第三次尝试，不能据它声称第一次反思后就已经学会跨轮修订。

## S4 · 剩余目标与重试路径

**完整英文指令：**[单独文本](../../prompts/reflection_candidates/s4_remaining_goals_v1.draft.txt)。

```text
You will be given the history of a past experience in which you were placed in an environment and given a task to complete. You were unsuccessful in completing the task. Do not summarize your environment, but rather think about the strategy and path you took to attempt to complete the task. Devise a concise, new plan of action that accounts for your mistake with reference to specific actions that you should have taken. For example, if you tried A and B but forgot C, then devise a plan to achieve C with environment-specific actions. You will need this later when you are solving the same task. Give your plan after "Plan".

Use the task description to check the required object, state, quantity, and destination, where applicable. Identify which required conditions lacked confirmed completion at the end of the last attempt. Give an ordered retry plan that covers those gaps and the prerequisites that must be repeated after reset. Preserve required counts and distinguish different objects when more than one is needed. Do not treat seeing, taking, or processing one object as completion of the whole task. Do not invent unknown object locations.
```

**相对 B 改了什么：**原版已有“尝试 A/B、遗漏 C 时补 C”的一般提示。S4 将遗漏检查具体化为物体、状态、数量、目的位置和完成证据；再把上轮剩余条件与重置后需要重做的前置步骤连接起来。数量要求来自任务原文，不依赖 task_id 或隐藏成功条件。

**盘子：原问题 → 期望改善。**上轮已拿取、冷却，未完成的是放进柜子。重试计划不能只写“现在去放”，因为重置后需要重新拿盘子并冷却。

```text
Plan: The goal requires a cooled plate inside a cabinet. In the last attempt, taking and cooling were confirmed, but cabinet placement was not. After reset: take plate 3 from diningtable 1; cool it with fridge 1; go to cabinet 1 and open it if closed; put plate 3 inside. Reaching or opening the cabinet alone does not complete the goal.
```

**锅铲：原问题 → 期望改善。**在第二次反思时，已确认完成的锅铲放置数量是 0/2。应计划两件不同物体的拿取与放置；不能从第三轮偷取“已完成 1/2”的信息。

```text
Plan: The goal requires two different spatulas in a drawer. The last attempt confirmed zero spatulas placed, and their locations are unknown. After reset, search for the first spatula, take it, open a drawer if needed, and place it inside. Then find and take a different second spatula and place it in the same drawer. Confirm both placements; one is insufficient.
```

**能支持到哪里：**第三轮只放入一把，说明数量缺口值得关注，却不能证明它是当轮失败的唯一内部原因。S4 不解决所有搜索效率问题：即使明确需要两把，也可能在动作预算内找不到第二把。

## S5 · 去重与信息密度

**完整英文指令：**[单独文本](../../prompts/reflection_candidates/s5_density_v1.draft.txt)。

```text
You will be given the history of a past experience in which you were placed in an environment and given a task to complete. You were unsuccessful in completing the task. Do not summarize your environment, but rather think about the strategy and path you took to attempt to complete the task. Devise a concise, new plan of action that accounts for your mistake with reference to specific actions that you should have taken. For example, if you tried A and B but forgot C, then devise a plan to achieve C with environment-specific actions. You will need this later when you are solving the same task. Give your plan after "Plan".

Put the actionable correction first. State each fact or instruction once. Omit unrelated objects, repeated alternatives, and generic promises to try again. Keep the details needed to execute the retry plan, including required quantities, ordering, and prerequisites. Compress repeated wording rather than deleting necessary steps. Stop when the plan is complete instead of continuing to repeat it.
```

**相对 B 改了什么：**原版已经要求 concise。S5 进一步明确：纠错动作优先、每条信息一次、删除无关对象和反复承诺、保留数量与顺序、写完即停。没有额外设置字数或 token 上限，也没有把完整任务压成单个动作。

**盘子：原问题 → 期望改善。**原反思重复多次“找不到就继续找其他桌子或柜子”。期望只保留必要的重试步骤，条件分支最多表述一次。下面是一份紧凑且正确的人工示意；其中正确的事实和工具选择并非 S5 单独能够保证。

```text
Plan: After reset, take plate 3 from diningtable 1, cool it with fridge 1, then go to cabinet 1, open it if closed, and put the plate inside. Once the plate is found, avoid spending the remaining actions searching other cabinets.
```

**锅铲：原问题 → 期望改善。**原反思反复承诺再寻找、再放置。期望把重复句压成一次完整安排，同时保留原任务的 two；不把两件物品压成只放一件。

```text
Plan: Search for two different spatulas. Take and place the first in an open drawer, then find and place the second there. Check object identity before taking it and confirm both placements.
```

**能支持到哪里：**必须区分内容质量与表达压缩。若盘子反思变短，却仍称没找到并使用 stoveburner，S5 只能算减少重复；若锅铲反思缩成“找一把放进去”，则丢失必要数量，不能算成功。

## 完整请求怎样与原版保持一致

现有原始请求由固定指令与上下文后缀拼接。未来接入时，只替换第一部分：

```text
完整请求 = 本版完整指令 + 原 B 请求从 " Here are two examples:" 开始的完整后缀
```

后缀依次包含以下内容，本文中的字段名只是说明运行时输入，不是让模型输出的内容：

1. 原有 `Here are two examples:` 与 [reflexion_few_shot_examples.txt](../../data/reflexion/reflexion_few_shot_examples.txt) 的两份示例；
2. 原机制提取的当次失败场景和轨迹；
3. 当旧记忆非空时，原有 `Plans from past attempts:` 及 `Trial #0: ...` 等旧反思条目；为空时该块省略；
4. 原有 `New plan:` 结尾。

不把本页人工示意、预先算好的完成清单、后续尝试结果或隐藏任务信息放入后缀。S1 的核验、S2 的诊断、S3 的比较和 S4 的目标核对，都要求同一个反思模型在原有一次生成中完成；没有新增提取、审核、改写调用。S3 仍保留旧记忆，不执行删除或程序化更新。

## 怎样判断预期是否真的发生

| 方向 | 盘子需要观察到的改变 | 锅铲需要观察到的改变 | 不能冒称的效果 |
| --- | --- | --- | --- |
| S1 | 正确承认拿取和冷却成功，证据来自本次反馈 | 区分 dishsponge 与 spatula，不虚构位置或已完成数量 | 一段正确引文不能证明整条反思都正确 |
| S2 | 指出漏执行 put，停止把问题解释为找不到 | 识别错误物体及未拿取即放置，原因不明处保留不确定性 | 无效动作的唯一原因已被证明 |
| S3 | 明确修订未找到及 stoveburner 的旧建议 | 保留寻找目标的有效建议，补入本轮暴露的错误物体问题 | 与旧文本不同就代表有效更新 |
| S4 | 写全重置后的拿取、冷却、放置顺序 | 从 0/2 开始覆盖两件不同锅铲的放置 | 清单本身已解决搜索或保证第二件能找到 |
| S5 | 去掉循环搜索描述且保留必要步骤 | 去掉反复承诺且保留 two、顺序和前置条件 | 变短就代表事实、诊断或任务结果变好 |

当前阶段只交付文本与预期，不产生上述质量指标或成功率的实验数值。论文与作者实现依据沿用[前一份调研](../papers/reflection-remedies-2026-11-23.md)，错误口径沿用[五类错误表](../experiments/reflection-error-taxonomy.md)。

## 静态核验记录

已核对 B 摘录与原函数指令一致；五份候选各由同一 B 原文加本方向一段组成；本页完整指令与独立文本对应。核对了案例的反思时点及原始反馈，特别区分第二轮可见事实与第三轮后验信息。未修改原日志、配置、actor、反思函数、两份原示例或旧 C01 v1；没有执行模型推理。
