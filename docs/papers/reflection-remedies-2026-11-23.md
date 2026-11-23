# 针对五类反思错误的论文依据与候选方案

2026-11-23｜状态：文献与设计分析完成；候选未运行，新增 GPU 用量 **0**。

后续交付：[S1–S5 完整提示词、原版对照与案例推演](../reports/S1-S5-prompt-drafts.md)已把本页片段细化为五份独立 v1 草案，包含盘子与锅铲的逐方案解释；以该报告及其链接文本作为完整草案。本页保留文献依据与最初设计思路。

## 判断与范围

建议优先考虑 **S1 观察证据约束**，它直接承接已选的 C01，针对证据最明确的事实矛盾；**S4 剩余目标核对**是另一项值得单独检验的候选。S2 针对失败归因，S3 针对跨轮更新，S5 作为减少重复的轻量对照。优先级是基于当前案例和改动可解释性的研究判断，并非有效性排名。

错误定义统一见[五类错误表](../experiments/reflection-error-taxonomy.md)。本次查阅论文正文、附录及作者仓库，不采用 GitHub 星数作为方法依据。下面明确区分“原论文做了什么”和“本项目可以借鉴什么”；所有英文段落都是本项目的**指令片段草案**，不是作者原文，也不是已接入的提示词。

合规边界沿用[主计划](../planning/plan.md)：固定 Qwen2.5-1.5B-Instruct Q4_K_M、原 actor、两份反思示例、输入轨迹、旧反思记忆及其注入方式；只改变英文反思指令。每次仍只生成一次反思，最多 256 token；不增加检索、验证器、模型调用、训练、环境状态接口或人工答案。原始观察仍完整按原机制输入，不预先提取或重写成另一套输入。

S1–S5 是候选目录，不是五个获批实验，也不自动替换 C01 v1。正文中的 CD、盘子、锅铲等仅用于解释已有证据，不写进通用提示词或新增 few-shot 示例。

## 论文与 GitHub 提供了什么依据

| 来源与核对位置 | 作者的具体做法 | 可以借鉴的部分 / 不能直接照搬的部分 |
| --- | --- | --- |
| **Reflexion**：[论文](https://arxiv.org/abs/2303.11366)；[固定版本反思函数](https://github.com/noahshinn/reflexion/blob/218cf0ef1df84b05ce379dd4a8e47f17766733a0/alfworld_runs/generate_reflections.py)，`_generate_reflection_query` | 原指令已经要求简洁、具体的新计划，输入中已有历史轨迹和旧计划 | 本项目 B 已具备这些要求；不能把“多反思一下”“简洁具体”包装成新方法。改进应有明确的新约束 |
| **ReAct，ICLR 2023**：[论文](https://arxiv.org/abs/2210.03629)；[作者 ALFWorld 示例](https://github.com/ysymyth/ReAct/blob/master/prompts/alfworld_3prompts.json)，`react_cool_0`、`react_puttwo_0` | 推理随观察更新计划；冷却示例区分拿取、冷却和放置，两物品示例分开处理第一件和第二件 | 支持“依据观察追踪进展与剩余子目标”的设计。原 actor 已沿用同类方法，新增价值只能来自反思端更明确的检查；不修改 actor 或替换示例 |
| **DEPS，NeurIPS 2023**：[论文 §3.2、附录 A.1/G.2](https://arxiv.org/html/2302.01560v3)；[作者提示词](https://github.com/CraftJarvis/MC-Planner/blob/main/data/deps_prompt.txt) | 先描述失败时的状态，再解释缺失的前置条件并重新规划；仓库示例随物品库存变化修正所需工具、材料和数量 | 支持具体失败诊断及目标缺口分析。只借入一次反思的组织方式，不引入逐步 planner/controller、额外解释调用或训练 selector。仓库示例是 Minecraft，ALFWorld 提示在论文附录中 |
| **Self-Refine，NeurIPS 2023**：[论文 §2、反馈质量消融及附录 H](https://arxiv.org/html/2303.17651v2)；[数学反馈示例](https://github.com/madaan/self-refine/blob/main/data/prompt/gsm/feedback.txt)；[缺失概念反馈示例](https://github.com/madaan/self-refine/blob/main/docs/commongen_feedback.txt) | 反馈定位具体错误并提出可操作修改；消融比较具体反馈、泛化反馈和无反馈；缺失概念示例只指出未覆盖项目 | 支持定位具体失败步骤和任务缺项。完整方法会循环调用反馈与改写，不能整套接入；其结果不是对本项目 1.5B 模型的保证 |
| **ExpeL，AAAI 2024**：[论文 §4.2](https://arxiv.org/html/2308.10144v3)；[作者规则更新模板](https://github.com/LeapLabTHU/ExpeL/blob/main/prompts/templates/human.py)，`FORMAT_RULES_OPERATION_TEMPLATE` | 对已有经验作增补、修订、赞同或否定；当前代码显式列出 `AGREE / REMOVE / EDIT / ADD`，并要求避免重复规则 | 支持“旧建议应接受新证据检验”。本项目只在新反思里修正旧建议，不删除旧记忆；不引入跨任务规则库、成功轨迹检索或额外提炼模型 |

ExpeL 正文以 `ADD / EDIT / DOWNVOTE / UPVOTE` 和计数删除说明规则维护，所读代码模板则用上述四个操作名。二者共同支持“有证据地维护经验”，不能把代码措辞当成论文完全一致的实现。

还需保留两条限制性证据：DEPS 的 ALFWorld 小规模测试中，所比较规划方法在 Pick Two & Place 类别均为零成功，不能据它声称“数量核对已能解决双物品任务”；[SCORE，Findings ACL 2024](https://aclanthology.org/2024.findings-acl.924/)（[作者仓库](https://github.com/yunx-z/SCORE)）显示，在其数学与常识推理设置中，弱自验证器限制了小模型的自纠正收益。SCORE 使用训练与验证器，超出本项目范围；这里只用它提醒：反思文本变好与执行成功必须分别检查。

## S1 · 用观察证据约束反思事实

**针对：**E1；并可能减轻由错误事实引起的 E2。直接承接 C01，建议优先。

**改法：**只要求模型用现有反馈校验关键事实，区分已经看到、已经拿取、处理成功和仍未知的信息；至多引用一小段必要证据。它需要检查事实，但不重述整个环境。

```text
Check factual claims against the observed feedback. Distinguish seeing an object, taking it, and successfully changing its state. Support the key factual claim behind your correction with one short feedback excerpt; if the evidence is insufficient, say what is unknown. Use these facts to correct the retry plan without retelling the environment.
```

**本地案例：**CD 的拾取成功已经在反思输入中，却被写成未找到。期望变化是承认上次拿到过 CD，再给出后续行动；不能仅生成一条正确引文，却保留其他互相矛盾的判断。盘子同理。

**依据与推断：**ReAct 利用观察追踪行动进展，DEPS 用失败时状态约束解释，支持这个设计方向；“限制为一段短反馈并用于核验事实”是本项目的提示词假设，没有现成的同模型效果证据。

**风险与判据：**长引文挤占计划空间，小模型也可能引错或断章取义。关注 E1 是否减少、引文是否真的支持判断，以及下次动作是否采用修正。事实准确但行动没有改善，只能报告局部收益。

## S2 · 从失败动作检查前置条件

**针对：**E2；适合黄油刀的无效动作及错误归因。

**改法：**把“我为什么失败”具体化为“哪一步没生效—当时缺少什么条件—重试如何修复”。若轨迹无法区分原因，保留不确定性。部分任务的障碍是根本没找到物体，不强迫每次都编一个无效动作。

```text
Identify the main failed action or uncompleted step and its observed outcome. Check which prerequisite was missing or unconfirmed at that point, using the history rather than assuming a cause. If the cause cannot be determined, say so. Give the concrete correction needed before retrying that step.
```

**本地案例：**黄油刀轨迹能确认清洁动作没生效，且在该动作前没有成功拿取记录；这比“洗成了水槽”更有依据。后一轮实际先拿取再清洁成功，支持检查拿取前置条件，但不能据此断言所有 `Nothing happens.` 都由未拿物体造成。

**依据与推断：**DEPS 的关键组织方式正是状态描述、前置条件解释和修正计划；Self-Refine 的反馈质量消融支持具体、可操作的反馈。压缩到课程原有的一次反思调用，仍是本项目需要验证的适配。

**风险与判据：**容易把解释写成貌似合理的故事。检查归因是否有观察支持、纠错动作是否对应缺失条件；不以文字流畅度或解释长度评分。

## S3 · 用新证据修订旧建议

**针对：**E3；适合第二次失败后的反思。

**改法：**利用原请求已包含的旧计划与本次轨迹，保留仍成立的建议，明确撤回或改写被新证据推翻的部分。不要求为了不同而不同。

```text
When past plans are provided, compare their advice with the latest attempt. Keep advice that remains supported, explicitly correct advice contradicted by new feedback, and add only newly needed guidance. If no relevant evidence changed, do not invent a change. Make the revised retry plan self-contained.
```

**本地案例：**盘子第二轮已经拿取并冷却，新反思应该修正“没找到”的旧判断，指出上轮没有完成最终放置。原记忆机制仍会保留旧反思，所以新文字需要明确哪项旧判断不再成立。

**依据与推断：**ExpeL 的经验维护包含保留、编辑、增补和移除；这里借其修订原则，应用于同一任务的旧反思。没有执行 ExpeL 的跨任务提炼、规则计数、删除或检索机制。

**风险与判据：**小模型可能不会正确比较两段文字；旧错误仍留在上下文中，也可能继续影响 actor。只在“旧建议与新证据需要对照”的样本上评价更新是否正确，不用字符串差异率替代质量。每题至多三次尝试，因此此方案直接影响的主要是第三次尝试。

## S4 · 明确剩余目标与完整重试路径

**针对：**E4；同时帮助发现遗漏进展的 E1。

**改法：**从已有自然语言任务提取物体、目标状态、数量和目的位置；对照上次反馈，指出尚未满足的条件，给出有顺序的重试计划。已完成子目标指上轮进展，不能直接当成重置后的状态。

```text
Use the task description to check the required object, state, quantity, and destination. Identify which required conditions lacked confirmed completion in the last attempt. Give an ordered retry plan that covers those gaps and the prerequisites that must be repeated after reset. Do not treat seeing, taking, or processing one object as completion of the whole task.
```

**本地案例：**两把锅铲不能停在“拿一把、放一把”，计划应覆盖第二件不同物品；盘子上轮完成冷却但未放入柜子，需要突出放置缺口，同时在新一轮重做拿取和冷却。位置未知时写搜索，不填入未观察到的位置答案。

**依据与推断：**ReAct 作者的 `react_puttwo_0` 显式区分第一件、第二件物品，`react_cool_0` 区分拿取、冷却、放置；Self-Refine 的缺失概念反馈提供“核对未覆盖条件”的类比。这些支持结构设计，未验证我们的反思端清单。

**风险与判据：**完整计划可能变长，模型可能错误计算数量或把上轮状态带到新一轮。检查剩余条件是否正确、计划是否覆盖数量和依赖，以及 actor 是否执行。已经在最后一次尝试才出现的“一把已放好”，只能作错误分析，不能偷偷补一次反思或重试。

## S5 · 去重并优先保留行动信息

**针对：**E5；适合作为轻量表达对照。

**改法：**只调整信息组织：关键纠错优先，每条信息只说一次，保留必要步骤和数量，完成后停止。保持后端 256 token 上限。

```text
Put the actionable correction first. State each fact or instruction once. Omit unrelated objects, repeated alternatives, and generic promises. Keep the details needed to execute the retry plan, including required quantities, ordering, and prerequisites. Stop when the plan is complete.
```

**本地案例：**删除放书反思中的连续重复放置句，以及 CD 反思中与任务无关的钥匙串、笔搜索清单。目标是让有效内容占比提高，不要求把多步任务压成一个动作。

**依据与推断：**Self-Refine 强调具体可操作反馈，其缺失概念示例也展示了有针对性的短反馈；但这些不是“缩短 ALFWorld 反思就会提高成功率”的直接证据。原 Reflexion 本来就要求简洁，S5 的新约束在于明确去重和排除无关内容，依据强度主要来自本地重复现象。

**风险与判据：**短文可能省掉必要条件，且小模型可能不遵守停止指令。需同时检查重复/无关内容、必要信息覆盖、到限情况与后续行动；仅 token 下降不算任务效果提升。

## 候选选择建议与当前状态

| 候选 | 建议位置 | 理由 | 还不能宣称什么 |
| --- | --- | --- | --- |
| S1 | 优先，作为 C01 后续细化参考 | 本地存在明确事实矛盾，改动目的容易核验 | 引用反馈就能保证事实正确或任务成功 |
| S4 | 第二个值得单独考虑的候选 | 直接对应数量遗漏、进度与最后一步，能连接反思和行动 | 清单已解决双物品任务 |
| S2 | 诊断方向候选 | 有 DEPS 的直接结构依据，本地有错误归因案例 | 无效反馈能唯一确定原因 |
| S3 | 跨轮更新方向候选 | 四对文本完全重复；盘子有明显新增进展 | 改写文本等于学习，或能影响第二次尝试 |
| S5 | 轻量对照或后续配套 | 十条均到限且存在重复、无关内容 | 更短就是更好 |

暂不把五段一次全部拼进提示词：会难以判断哪项有效，也给 1.5B 模型增加指令负担。旧 C01 v1 草案和预算报告保留；本次新增的是错误口径、文献依据和待选方案。方向选择与实验预算尚待用户决定，没有启动模型、接入新候选或运行任何实验。

后续若运行，所有候选仍用同一开发任务、输入、种子和预算作 B/C 配对；主结果看任务成功，五类错误用于解释“文本是否变好、行为是否跟随”。外部论文的模型、框架与评测不同，其结果不作为本项目的预期提升数。

检索日期：2026-11-23。GitHub `main/master` 链接指向检索时阅读的作者文件；Reflexion 使用项目已固定版本。没有复制外部训练数据或示例到本项目提示词。
