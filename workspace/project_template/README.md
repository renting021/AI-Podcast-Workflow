# 单期播客项目

建议文件：

- `audio.m4a` 或 `audio.mp3`
- `transcript.jsonl`
- `outline.json`
- `claims.json`
- `style_contract.json`
- `speaker_map.json`
- `article_part_*.md`
- `article_draft.md`
- `article_final.md`
- `quality_report.json`
- `dialogue_quality.json`
- `revision_log.jsonl`
- `style_feedback.jsonl`
- `feishu_doc_url.txt`

访谈或圆桌节目必须使用 `$refine-podcast-dialogue`，并在 `quality_report.json` 与 `dialogue_quality.json` 都通过后才生成 `article_final.md`。发布前必须由用户确认最终稿。
