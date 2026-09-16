#!/usr/bin/env python3
"""
小宇宙：解析单集页 / 播客页的 __NEXT_DATA__，取音频直链（多为 m4a）下载到指定目录。

用法（在 SeaSee 项目根目录运行）：
  .podcast-venv/bin/python xiaoyuzhou_audio_pipeline.py --url https://www.xiaoyuzhoufm.com/episode/<eid>
  .podcast-venv/bin/python xiaoyuzhou_audio_pipeline.py --podcast https://www.xiaoyuzhoufm.com/podcast/<pid>
  .podcast-venv/bin/python xiaoyuzhou_audio_pipeline.py --podcast <pid> --count 3

也可只传 ID（自动补全域名与路径）：
  .venv/bin/python experiment/xiaoyuzhou/xiaoyuzhou_audio_pipeline.py --url 69b65d48caaea1fb3b5575cc
  .venv/bin/python experiment/xiaoyuzhou/xiaoyuzhou_audio_pipeline.py --podcast 64034de46845518a6a9cbce6
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = ROOT / "out"

NEXT_DATA_OPEN = '<script id="__NEXT_DATA__" type="application/json">'
# 小宇宙 CDN 对「Chrome/xxx」类 UA 常返回 403，Safari 风格可通过
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
)


def _safe_filename(name: str, max_len: int = 120) -> str:
    for c in '<>:"/\\|?*\n\r\t':
        name = name.replace(c, "_")
    name = name.strip(" .")
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "untitled"


def _normalize_episode_input(s: str) -> str:
    s = s.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if re.fullmatch(r"[0-9a-f]{24}", s, re.I):
        return f"https://www.xiaoyuzhoufm.com/episode/{s}"
    return s


def _normalize_podcast_input(s: str) -> str:
    s = s.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if re.fullmatch(r"[0-9a-f]{24}", s, re.I):
        return f"https://www.xiaoyuzhoufm.com/podcast/{s}"
    return s


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"HTTP 错误 {e.code}: {url}", file=sys.stderr)
        raise SystemExit(1) from e
    except urllib.error.URLError as e:
        print(f"网络错误: {e.reason}", file=sys.stderr)
        raise SystemExit(1) from e


def extract_next_data_json(html: str) -> dict[str, Any]:
    i = html.find(NEXT_DATA_OPEN)
    if i < 0:
        print("错误：页面中未找到 __NEXT_DATA__（可能非小宇宙页或结构已变）。", file=sys.stderr)
        raise SystemExit(1)
    j = html.find("</script>", i)
    if j < 0:
        print("错误：__NEXT_DATA__ 未闭合。", file=sys.stderr)
        raise SystemExit(1)
    raw = html[i + len(NEXT_DATA_OPEN) : j]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"错误：解析 __NEXT_DATA__ JSON 失败: {e}", file=sys.stderr)
        raise SystemExit(1) from e


def page_props(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("props", {}).get("pageProps", {}) or {}


def audio_url_from_episode_dict(ep: dict[str, Any]) -> str | None:
    enc = ep.get("enclosure") or {}
    u = enc.get("url") if isinstance(enc, dict) else None
    if u:
        return str(u)
    media = ep.get("media") or {}
    if isinstance(media, dict):
        src = media.get("source") or {}
        if isinstance(src, dict) and src.get("url"):
            return str(src["url"])
    return None


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    print("下载:", url[:80], "..." if len(url) > 80 else "")
    print(" ->", dest.resolve())
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
            shutil.copyfileobj(resp, f)
    except urllib.error.HTTPError as e:
        print(f"下载失败 HTTP {e.code}", file=sys.stderr)
        raise SystemExit(1) from e
    except urllib.error.URLError as e:
        print(f"下载失败: {e.reason}", file=sys.stderr)
        raise SystemExit(1) from e


def ext_from_url(url: str) -> str:
    m = re.search(r"\.([a-zA-Z0-9]{1,8})(?:\?|$)", url)
    if m:
        ext = m.group(1).lower()
        if ext in ("m4a", "mp3", "mp4", "aac", "wav", "ogg"):
            return ext
    return "m4a"


def run_episode_page(url: str, output_dir: Path) -> None:
    url = _normalize_episode_input(url)
    html = fetch_html(url)
    data = extract_next_data_json(html)
    pp = page_props(data)
    ep = pp.get("episode")
    if not isinstance(ep, dict):
        print("错误：该 URL 不是单集页（pageProps 无 episode）。", file=sys.stderr)
        raise SystemExit(1)
    if ep.get("isPrivateMedia"):
        print("错误：该单集为私有/付费音频，页面未提供直链。", file=sys.stderr)
        raise SystemExit(1)
    audio = audio_url_from_episode_dict(ep)
    if not audio:
        print("错误：未解析到音频 URL。", file=sys.stderr)
        raise SystemExit(1)
    title = ep.get("title") or "episode"
    ext = ext_from_url(audio)
    fname = _safe_filename(str(title)) + f".{ext}"
    download_file(audio, output_dir / fname)


def run_podcast_page(url: str, count: int, output_dir: Path) -> None:
    url = _normalize_podcast_input(url)
    html = fetch_html(url)
    data = extract_next_data_json(html)
    pp = page_props(data)
    pod = pp.get("podcast")
    if not isinstance(pod, dict):
        print("错误：该 URL 不是播客页（pageProps 无 podcast）。", file=sys.stderr)
        raise SystemExit(1)
    episodes = pod.get("episodes") or []
    if not isinstance(episodes, list) or not episodes:
        print("错误：播客页未包含单集列表（可能需登录或页面结构已变）。", file=sys.stderr)
        raise SystemExit(1)
    podcast_title = str(pod.get("title") or "podcast")
    safe_pod = _safe_filename(podcast_title, max_len=60)
    n_ok = 0
    for ep in episodes[:count]:
        if not isinstance(ep, dict):
            continue
        if ep.get("isPrivateMedia"):
            print("跳过（私有/付费）:", ep.get("title", ""))
            continue
        audio = audio_url_from_episode_dict(ep)
        if not audio:
            print("跳过（无音频链）:", ep.get("title", ""))
            continue
        ep_title = ep.get("title") or ep.get("eid") or "episode"
        ext = ext_from_url(audio)
        fname = f"{safe_pod} - {_safe_filename(str(ep_title))}.{ext}"
        download_file(audio, output_dir / fname)
        n_ok += 1
    if n_ok == 0:
        print("错误：没有成功下载任何单集。", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="小宇宙：单集页 / 播客页 → 解析 __NEXT_DATA__ → 下载音频到 experiment/xiaoyuzhou/out/",
    )
    parser.add_argument(
        "--url",
        metavar="EPISODE_URL_OR_EID",
        help="单集页完整 URL 或 24 位 eid",
    )
    parser.add_argument(
        "--podcast",
        metavar="PODCAST_URL_OR_PID",
        help="播客页完整 URL 或 24 位 pid；与 --url 二选一",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="与 --podcast 联用：下载列表中最新的若干条（默认 1）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="音频输出目录；相对路径按工作流目录解析（默认 out）",
    )
    args = parser.parse_args()

    if bool(args.url) == bool(args.podcast):
        parser.error("请只指定其一：--url（单集）或 --podcast（播客，拉最新若干条）")

    if args.count < 1:
        parser.error("--count 至少为 1")

    output_dir = args.output_dir.expanduser()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir = output_dir.resolve()

    os.chdir(ROOT)

    if args.url:
        run_episode_page(args.url, output_dir)
    else:
        run_podcast_page(args.podcast, args.count, output_dir)

    print("完成。文件应在:", output_dir)


if __name__ == "__main__":
    main()
