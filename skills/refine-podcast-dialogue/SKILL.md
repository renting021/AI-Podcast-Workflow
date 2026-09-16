---
name: refine-podcast-dialogue
description: Restore and preserve the live dialogue feel of long-form podcast articles while preventing cross-chunk style drift. Use when Codex writes, rewrites, reviews, or repairs interview/podcast Markdown from transcripts; when multiple writers or agents handle different time ranges; when later sections become third-person summaries; or when the user asks for 对话体、现场感、主持人与嘉宾问答、完整还原、文风统一、自迭代质检.
---

# 播客对话体精修

把长播客整理为去除口疾但保留问答推进、人物关系和现场节奏的文章。使用确定性检查定位跨分段文风漂移，并只重写失败章节，直至通过或触发人工阻断。

## 必须产生的中间产物

在单期项目目录保存：

- `style_contract.json`：本期文体、标签和允许的转述范围；
- `speaker_map.json`：说话人及归因置信度；
- `article_part_*.md`：带时间范围的分段稿；
- `dialogue_quality.json`：确定性文风检查结果；
- `revision_log.jsonl`：每轮失败、修改范围和结果；
- `article_final.md`：仅在全部硬门槛通过后生成；
- `style_feedback.jsonl`：用户反馈形成的候选规则，不得直接覆盖 Skill。

## 工作流

### 1. 锁定文体契约

先读取 `references/style-contract.md`。如果源内容是访谈、圆桌或用户要求“现场感”，默认使用 `interview_dialogue`。

若用户已经认可开头或某一章节，把它登记为 `style_reference`。后续所有分段必须模仿其标签形式、问答密度、段落长度和中英文术语风格，不得自行选择另一种叙述体。

### 2. 建立说话人映射

从带时间戳转录中识别说话人轮次并记录置信度：

- 高置信度：上下文点名、主持人明确呼叫、稳定声音标签；可以使用姓名；
- 中置信度：能判断主持人或嘉宾角色，但无法确认具体嘉宾；使用 `主持人` 或 `嘉宾`；
- 低置信度：无法可靠区分；使用 `说话人未确认`，或回到音频核对。

禁止为了现场感虚构姓名归属。角色标签优先于错误姓名。

### 3. 按对话单元分段

不要按固定字数或整点机械切断。以“主持人提出问题—嘉宾回答—追问或补充”作为最小写作单元。

长任务需要并行分段时：

1. 给每个分段相同的 `style_contract.json` 和同一份合格示例；
2. 相邻分段保留 60–120 秒转录重叠；
3. 每段开头承接上一段问题，结尾保留下一段的提问入口；
4. 禁止把问答改成“主持人问到／嘉宾表示／节目讨论认为”的连续转述；
5. 分段稿必须标明覆盖时间范围。

### 4. 合并时统一编辑

合并不是文件拼接。逐个检查分段接缝：

- 时间顺序是否连续；
- 主持人的问题是否保留；
- 嘉宾回答是否被第三方概括替代；
- 人名、角色标签和术语是否一致；
- 重叠区是否重复或遗漏；
- 前后章节的对话标签密度是否突变。

### 5. 运行确定性检查

执行：

```bash
python3 scripts/check_dialogue_consistency.py article_draft.md \
  --json-out dialogue_quality.json
```

检查器按章节计算对话标签、第三方转述信号、对话密度和跨章节突变。标题含“摘要、嘉宾介绍、来源、关键观点、说明”等内容时自动视为非对话豁免区。

任何长访谈章节出现以下情况必须失败：

- 没有对话标签，却出现第三方归因句；
- 对话标签密度低于契约阈值；
- 从上一章节的对话体突然变成转述体；
- 全文对话信号占比低于阈值。

### 6. 执行受控自迭代

读取 `references/iteration-policy.md`，最多自动迭代三轮：

1. 从 `dialogue_quality.json` 取得失败章节和行号；
2. 只读取该章节对应时间范围及前后重叠转录；
3. 保留观点、限定条件和时间顺序，重建问答；
4. 写入新版本，禁止直接覆盖上一轮；
5. 复查证据与说话人置信度；
6. 再次运行确定性检查；
7. 把修改原因和指标变化追加到 `revision_log.jsonl`。

连续两轮出现同一失败，或三轮后仍未通过时停止自动重写，报告阻断原因并请求人工判断。不得通过删除内容、伪造说话人或降低阈值制造“通过”。

### 7. 吸收用户反馈

把用户反馈记录为 `style_feedback.jsonl` 的候选规则，包括症状、证据、修复和适用范围。

只有满足以下任一条件，才允许更新 Skill 的参考规则：

- 用户明确批准把该反馈设为长期规则；
- 同一失败模式在至少两个独立播客项目中重复出现，并经人工确认。

更新后运行 `quick_validate.py`，并用历史失败样本和一个原本合格样本回归测试。不得让单次输出自动改写全局 Skill。

## 发布硬门槛

同时满足以下条件后才能生成最终稿并请求用户发布确认：

- 时间、主题、观点和证据覆盖检查通过；
- `dialogue_quality.json.status == "pass"`；
- 说话人低置信度位置已使用角色标签或完成核对；
- 分段接缝无文体突变、重复或遗漏；
- 用户已审阅最终稿。

未经用户确认，不发布或覆盖既有飞书版本。
