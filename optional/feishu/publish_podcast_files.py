#!/usr/bin/env python3
"""Send reviewed podcast Markdown files to one allowlisted Feishu bridge group."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

import lark_oapi as lark

from feishu_codex_bridge import delivery
from feishu_codex_bridge.config import Settings
from feishu_codex_bridge.groups import CreatedGroupStore


def article_title(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0].strip()
    return first_line.removeprefix("# ").strip() or path.stem


def safe_filename(title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", title).strip(" .")
    return f"{cleaned[:100] or '播客终稿'}.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="发布已审阅的播客 Markdown 到飞书群")
    parser.add_argument("--group", required=True, help="桥接创建的精确群名")
    parser.add_argument("--file", action="append", required=True, type=Path)
    args = parser.parse_args()

    source_files = [path.expanduser().resolve() for path in args.file]
    for path in source_files:
        if not path.is_file():
            raise FileNotFoundError(path)

    settings = Settings.load()
    database = settings.workspace.parent / "data" / "messages.sqlite3"
    chat_id = CreatedGroupStore(database).get_unique_by_name(args.group)
    if chat_id is None:
        raise RuntimeError(f"未找到已由桥接创建的群聊：{args.group}")
    if chat_id not in settings.allowed_chat_ids:
        raise RuntimeError(f"目标群未在本机白名单中：{args.group}")

    client = (
        lark.Client.builder()
        .app_id(settings.app_id)
        .app_secret(settings.app_secret)
        .log_level(lark.LogLevel.WARNING)
        .build()
    )
    titles = [article_title(path) for path in source_files]

    # deliver_file also emits a legacy fixed caption. Suppress only that text
    # while preserving its tested upload, group allowlist and attachment-memory path.
    original_send = delivery._send_message

    def send_files_only(client_arg, chat_id_arg, msg_type, content):
        if msg_type == "text":
            return None
        return original_send(client_arg, chat_id_arg, msg_type, content)

    with tempfile.TemporaryDirectory(prefix="codex-podcast-publish-") as tmp:
        temporary_dir = Path(tmp)
        delivery._send_message = send_files_only
        try:
            for source, title in zip(source_files, titles, strict=True):
                packaged = temporary_dir / safe_filename(title)
                shutil.copyfile(source, packaged)
                delivery.deliver_file(settings, args.group, packaged, client=client)
        finally:
            delivery._send_message = original_send

    summary = f"已上传 {len(titles)} 期播客 Markdown 终稿：\n" + "\n".join(
        f"{index}. {title}" for index, title in enumerate(titles, start=1)
    )
    original_send(client, chat_id, "text", {"text": summary})
    print(json.dumps({"status": "sent", "group": args.group, "titles": titles}, ensure_ascii=False))


if __name__ == "__main__":
    main()
