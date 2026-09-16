# 飞书发布可选模块

这个目录只提供播客 Markdown 附件发布程序，不包含 App Secret、Token、用户或群 ID、SQLite 数据库、日志和钥匙串内容。

## 新电脑必须重新完成

1. 安装并测试本地 FeishuCodexBridge；
2. 使用同一个飞书应用的 App ID，并把 App Secret 重新写入新电脑的 macOS 钥匙串；
3. 重新建立用户和群白名单；
4. 确认目标群由桥接识别且名称唯一；
5. 发送一条测试消息，验证机器人能够收到并回复；
6. 在用户确认终稿后，才执行附件发布。

不要复制旧电脑中的以下目录或文件：

- `data/*.sqlite*`；
- `data/attachments/`；
- `logs/`；
- 钥匙串导出文件；
- 包含用户 `open_id`、群 `chat_id` 或消息 ID 的文件。

## 发布程序

通过迁移包的 `--include-feishu-tools` 安装后，工作区会出现 `publish_podcast_files.py`。

它必须使用 FeishuCodexBridge 自己的 Python 环境和源码路径运行。示例中的路径是新电脑默认运行目录：

```bash
CODEX_BRIDGE_WORKSPACE="$HOME/Library/Application Support/FeishuCodexBridge/workspace" \
PYTHONPATH="$HOME/Library/Application Support/FeishuCodexBridge/src" \
"$HOME/Library/Application Support/FeishuCodexBridge/.venv/bin/python" \
publish_podcast_files.py \
  --group "精确群名" \
  --file "/播客项目/article_final.md"
```

程序会检查群是否唯一、是否在白名单中，并以独立 Markdown 附件上传。它不会创建群、修改权限或绕过发布确认。
