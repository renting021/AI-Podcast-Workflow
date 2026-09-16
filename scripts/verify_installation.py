#!/usr/bin/env python3
"""Verify a packaged or installed Codex podcast workflow without network access."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


WORKSPACE_FILES = (
    "AGENTS.md",
    "PODCAST_WORKFLOW.md",
    "quality_checklist.md",
    "requirements-podcast.txt",
    "xiaoyuzhou_audio_pipeline.py",
    "transcribe_mlx.py",
    "check_transcript.py",
    "merge_podcast_article.py",
    "project_template/README.md",
    "project_template/episode.json",
    "project_template/speaker_map.json",
    "project_template/style_contract.json",
)

SKILL_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/style-contract.md",
    "references/iteration-policy.md",
    "scripts/check_dialogue_consistency.py",
)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True)


def main() -> int:
    # GUI-launched .command files may not inherit the user's shell PATH.
    extra_paths = ("/opt/homebrew/bin", "/usr/local/bin")
    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join((*extra_paths, current_path))

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.home() / "Documents" / "Codex podcast Product",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--allow-missing-runtime", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    skill = args.codex_home.expanduser().resolve() / "skills" / "refine-podcast-dialogue"
    checks: dict[str, dict[str, object]] = {}

    def record(name: str, passed: bool, detail: str) -> None:
        checks[name] = {"status": "pass" if passed else "fail", "detail": detail}

    is_target = platform.system() == "Darwin" and platform.machine() == "arm64"
    record("platform", is_target, f"{platform.system()} {platform.machine()}")

    missing_workspace = [name for name in WORKSPACE_FILES if not (workspace / name).is_file()]
    record(
        "workspace_files",
        not missing_workspace,
        "complete" if not missing_workspace else "missing: " + ", ".join(missing_workspace),
    )

    missing_skill = [name for name in SKILL_FILES if not (skill / name).is_file()]
    record(
        "skill_files",
        not missing_skill,
        "complete" if not missing_skill else "missing: " + ", ".join(missing_skill),
    )

    if not missing_skill:
        skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = re.match(r"\A---\n(.*?)\n---\n", skill_text, re.DOTALL)
        valid_frontmatter = bool(
            frontmatter
            and re.search(r"^name:\s*refine-podcast-dialogue\s*$", frontmatter.group(1), re.MULTILINE)
            and re.search(r"^description:\s*.+$", frontmatter.group(1), re.MULTILINE)
        )
        record("skill_frontmatter", valid_frontmatter, "valid" if valid_frontmatter else "invalid")

    syntax_failures: list[str] = []
    for name in ("xiaoyuzhou_audio_pipeline.py", "transcribe_mlx.py", "check_transcript.py", "merge_podcast_article.py"):
        path = workspace / name
        if not path.is_file():
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            syntax_failures.append(f"{name}:{exc.lineno}")
    checker = skill / "scripts" / "check_dialogue_consistency.py"
    if checker.is_file():
        try:
            compile(checker.read_text(encoding="utf-8"), str(checker), "exec")
        except SyntaxError as exc:
            syntax_failures.append(f"check_dialogue_consistency.py:{exc.lineno}")
    record(
        "python_syntax",
        not syntax_failures,
        "valid" if not syntax_failures else ", ".join(syntax_failures),
    )

    python_for_tests = sys.executable
    with tempfile.TemporaryDirectory(prefix="podcast-workflow-verify-") as temporary:
        temp = Path(temporary)
        transcript = temp / "transcript.json"
        transcript.write_text(
            json.dumps(
                {
                    "segments": [
                        {"start": 0.0, "end": 10.0, "text": "主持人提出问题"},
                        {"start": 10.0, "end": 20.0, "text": "嘉宾完整回答"},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        transcript_report = temp / "transcript-qc.json"
        transcript_check = run(
            [
                python_for_tests,
                str(workspace / "check_transcript.py"),
                str(transcript),
                "--duration",
                "20",
                "--json-out",
                str(transcript_report),
            ]
        )
        transcript_passed = (
            transcript_check.returncode == 0
            and transcript_report.is_file()
            and json.loads(transcript_report.read_text(encoding="utf-8")).get("status") == "pass"
        )
        record("transcript_checker", transcript_passed, transcript_check.stdout.strip() or transcript_check.stderr.strip())

        sample = temp / "article.md"
        sample.write_text(
            "# 测试稿\n\n## 完整问答（00:00–01:00）\n\n"
            "**主持人：** 这是一个用于验证迁移包的测试问题。它只检查程序能否识别稳定的对话标签、章节结构与对话密度，不代表真实播客内容。\n\n"
            "**嘉宾：** 这是对应的完整回答。验证程序会运行与正式工作流相同的确定性检查器，确认安装后的 Skill 可以读取文章、计算指标并输出 JSON 报告。为了超过最小章节长度，这里补充说明：测试不会访问网络，不会修改用户文档，也不会发送任何飞书消息。\n",
            encoding="utf-8",
        )
        dialogue_report = temp / "dialogue-qc.json"
        dialogue_check = run(
            [
                python_for_tests,
                str(checker),
                str(sample),
                "--json-out",
                str(dialogue_report),
            ]
        )
        dialogue_passed = (
            dialogue_check.returncode == 0
            and dialogue_report.is_file()
            and json.loads(dialogue_report.read_text(encoding="utf-8")).get("status") == "pass"
        )
        record("dialogue_checker", dialogue_passed, dialogue_check.stdout.strip() or dialogue_check.stderr.strip())

    runtime_python = workspace / ".podcast-venv" / "bin" / "python"
    if runtime_python.is_file():
        version_check = run(
            [
                str(runtime_python),
                "-c",
                "import importlib.metadata as m; print(m.version('mlx-whisper'))",
            ]
        )
        version = version_check.stdout.strip()
        record(
            "mlx_whisper_package",
            version_check.returncode == 0 and version == "0.4.3",
            f"version={version}" if version_check.returncode == 0 else version_check.stderr.strip(),
        )
        import_check = run([str(runtime_python), "-c", "import mlx_whisper; print('mlx_whisper import ok')"])
        import_detail = import_check.stdout.strip() or import_check.stderr.strip()
        if import_check.returncode == 0:
            record("metal_runtime", True, import_detail)
        elif "No Metal device available" in import_detail:
            checks["metal_runtime"] = {
                "status": "skip",
                "detail": "package installed; current headless/sandboxed session cannot access Metal",
            }
        else:
            record("metal_runtime", False, import_detail)
    elif args.allow_missing_runtime:
        checks["mlx_whisper_package"] = {
            "status": "skip",
            "detail": "runtime installation intentionally skipped",
        }
        checks["metal_runtime"] = {
            "status": "skip",
            "detail": "runtime installation intentionally skipped",
        }
    else:
        record("mlx_whisper_package", False, f"missing runtime: {runtime_python}")
        record("metal_runtime", False, f"missing runtime: {runtime_python}")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        record("ffmpeg", True, f"ffmpeg={ffmpeg}; ffprobe={ffprobe}")
    elif args.allow_missing_runtime:
        checks["ffmpeg"] = {"status": "skip", "detail": "runtime installation intentionally skipped"}
    else:
        record("ffmpeg", False, "ffmpeg or ffprobe not found")

    failed = [name for name, result in checks.items() if result["status"] == "fail"]
    print("播客工作流验证结果")
    for name, result in checks.items():
        symbol = {"pass": "✓", "fail": "✗", "skip": "-"}[str(result["status"])]
        print(f"{symbol} {name}: {result['detail']}")
    print(json.dumps({"status": "fail" if failed else "pass", "checks": checks}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
