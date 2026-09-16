# 自迭代策略

## 两种迭代

### 单期文章迭代

允许自动执行，最多三轮：

```text
draft
  → deterministic_check
  → locate_failed_sections
  → reread_source_with_overlap
  → rewrite_failed_sections_only
  → evidence_and_attribution_check
  → deterministic_check
```

每轮保留独立文件，例如 `article_iter_01.md`、`article_iter_02.md`，通过后才复制为 `article_final.md`。

`revision_log.jsonl` 每行至少记录：

```json
{"iteration":1,"failed_sections":["搜索为什么是模型自我进化的入口"],"reasons":["no_dialogue_labels"],"source_range":"24:00-25:59","changes":"恢复主持人提问与嘉宾回答","before_status":"fail","after_status":"pass"}
```

### 跨项目 Skill 迭代

默认只生成候选规则，不自动修改全局规则。

`style_feedback.jsonl` 每行至少记录：

```json
{"episode_id":"example","symptom":"分段交界后由对话体漂移为转述体","evidence":"24:00与分段边界重合","resolution":"共享风格契约并增加对话密度检查","generalized_rule":"分段写作必须共享合格样例并检查接缝","approved":false}
```

满足用户明确批准，或同一模式在两个独立项目重复且经人工确认后，才把候选规则提升到 `style-contract.md`。

## 迭代不变量

每轮都必须保持：

- 时间顺序不变；
- 原观点、限定条件和不确定性不丢失；
- 不增加原文没有的事实和引语；
- 不把低置信度说话人升级为具体姓名；
- 不通过缩短文章或放宽阈值消除失败。

## 停止条件

满足任一条件立即停止并请求人工判断：

- 连续两轮同一章节、同一原因失败；
- 三轮后仍未通过；
- 转录无法区分主持人与嘉宾；
- 修复现场感会要求猜测具体说话人；
- 文风检查与事实完整性检查发生冲突。

## 回归测试

Skill 规则更新后至少测试：

1. 一个历史文风漂移样本，必须失败并定位边界；
2. 一个原本合格的对话体样本，必须通过；
3. 一个摘要或来源章节，必须正确豁免。
