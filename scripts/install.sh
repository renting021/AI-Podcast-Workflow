#!/bin/zsh
set -eu

PACKAGE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROGRAM_NAME="./scripts/install.sh"
TARGET_WORKSPACE="$HOME/Documents/Codex podcast Product"
TARGET_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
FORCE=0
SKIP_RUNTIME=0
INSTALL_SYSTEM_DEPS=0
INCLUDE_FEISHU=0
PYTHON_OVERRIDE=""

usage() {
  print "用法：$PROGRAM_NAME [--workspace PATH] [--codex-home PATH] [--python PATH] [--force] [--skip-runtime] [--install-system-deps] [--include-feishu-tools]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace)
      [[ $# -ge 2 ]] || { usage; exit 64; }
      TARGET_WORKSPACE="$2"
      shift 2
      ;;
    --codex-home)
      [[ $# -ge 2 ]] || { usage; exit 64; }
      TARGET_CODEX_HOME="$2"
      shift 2
      ;;
    --python)
      [[ $# -ge 2 ]] || { usage; exit 64; }
      PYTHON_OVERRIDE="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --skip-runtime)
      SKIP_RUNTIME=1
      shift
      ;;
    --install-system-deps)
      INSTALL_SYSTEM_DEPS=1
      shift
      ;;
    --include-feishu-tools)
      INCLUDE_FEISHU=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      print -u2 "未知参数：$1"
      usage
      exit 64
      ;;
  esac
done

TARGET_WORKSPACE="${TARGET_WORKSPACE/#\~/$HOME}"
TARGET_CODEX_HOME="${TARGET_CODEX_HOME/#\~/$HOME}"
PYTHON_OVERRIDE="${PYTHON_OVERRIDE/#\~/$HOME}"
TARGET_SKILL="$TARGET_CODEX_HOME/skills/refine-podcast-dialogue"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  print -u2 "当前转录程序依赖 MLX Whisper，只支持 Apple 芯片 Mac（arm64）。"
  exit 65
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

if [[ $SKIP_RUNTIME -eq 0 && $INSTALL_SYSTEM_DEPS -eq 1 ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    print -u2 "未发现 Homebrew。请先安装 Homebrew，或手动安装 Python 3.12 与 FFmpeg。"
    exit 69
  fi
  command -v python3.12 >/dev/null 2>&1 || brew install python@3.12
  command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
fi

PYTHON_CMD=""
if [[ $SKIP_RUNTIME -eq 0 ]]; then
  if [[ -n "$PYTHON_OVERRIDE" ]]; then
    if [[ ! -x "$PYTHON_OVERRIDE" ]] || ! "$PYTHON_OVERRIDE" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)' >/dev/null 2>&1; then
      print -u2 -- "--python 必须指向可执行的 Python 3.10–3.13：$PYTHON_OVERRIDE"
      exit 69
    fi
    PYTHON_CMD="$PYTHON_OVERRIDE"
  else
    for candidate in python3.12 python3.11 python3.10 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)' >/dev/null 2>&1; then
        PYTHON_CMD="$(command -v "$candidate")"
        break
      fi
    done
  fi
  if [[ -z "$PYTHON_CMD" ]]; then
    print -u2 "未找到 Python 3.10–3.13。推荐安装 Python 3.12。"
    print -u2 "如果已安装 Homebrew，可重新运行：$PROGRAM_NAME --install-system-deps"
    exit 69
  fi
  if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    print -u2 "未找到 FFmpeg/FFprobe。"
    print -u2 "如果已安装 Homebrew，可重新运行：$PROGRAM_NAME --install-system-deps"
    exit 69
  fi
  if [[ -x "$TARGET_WORKSPACE/.podcast-venv/bin/python" ]] && ! "$TARGET_WORKSPACE/.podcast-venv/bin/python" -c 'import sys; raise SystemExit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)' >/dev/null 2>&1; then
    print -u2 "已有 .podcast-venv 的 Python 版本不兼容。请先把该目录改名保留，再重新安装。"
    exit 69
  fi
fi

typeset -a conflicts

scan_conflicts() {
  local source_root="$1"
  local target_root="$2"
  local source_file relative target_file
  while IFS= read -r -d '' source_file; do
    relative="${source_file#$source_root/}"
    target_file="$target_root/$relative"
    if [[ -e "$target_file" ]] && ! cmp -s "$source_file" "$target_file"; then
      conflicts+=("$target_file")
    fi
  done < <(find "$source_root" -type f -print0)
}

scan_conflicts "$PACKAGE_ROOT/workspace" "$TARGET_WORKSPACE"
scan_conflicts "$PACKAGE_ROOT/skills/refine-podcast-dialogue" "$TARGET_SKILL"
if [[ $INCLUDE_FEISHU -eq 1 && -e "$TARGET_WORKSPACE/publish_podcast_files.py" ]] && ! cmp -s "$PACKAGE_ROOT/optional/feishu/publish_podcast_files.py" "$TARGET_WORKSPACE/publish_podcast_files.py"; then
  conflicts+=("$TARGET_WORKSPACE/publish_podcast_files.py")
fi

if [[ ${#conflicts[@]} -gt 0 && $FORCE -eq 0 ]]; then
  print -u2 "检测到 ${#conflicts[@]} 个内容不同的同名文件，未执行安装："
  for item in "${conflicts[@]}"; do
    print -u2 "  $item"
  done
  print -u2 "确认需要更新时使用 --force；旧文件会先备份。"
  exit 73
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
WORKSPACE_BACKUP="$TARGET_WORKSPACE/.migration-backups/$STAMP"
SKILL_BACKUP="$TARGET_CODEX_HOME/.migration-backups/$STAMP/refine-podcast-dialogue"

copy_tree() {
  local source_root="$1"
  local target_root="$2"
  local backup_root="$3"
  local source_file relative target_file backup_file
  while IFS= read -r -d '' source_file; do
    relative="${source_file#$source_root/}"
    target_file="$target_root/$relative"
    if [[ -e "$target_file" ]] && cmp -s "$source_file" "$target_file"; then
      continue
    fi
    if [[ -e "$target_file" ]]; then
      backup_file="$backup_root/$relative"
      mkdir -p "$(dirname "$backup_file")"
      cp -p "$target_file" "$backup_file"
    fi
    mkdir -p "$(dirname "$target_file")"
    cp -p "$source_file" "$target_file"
  done < <(find "$source_root" -type f -print0)
}

copy_tree "$PACKAGE_ROOT/workspace" "$TARGET_WORKSPACE" "$WORKSPACE_BACKUP"
copy_tree "$PACKAGE_ROOT/skills/refine-podcast-dialogue" "$TARGET_SKILL" "$SKILL_BACKUP"

if [[ $INCLUDE_FEISHU -eq 1 ]]; then
  if [[ -e "$TARGET_WORKSPACE/publish_podcast_files.py" ]] && ! cmp -s "$PACKAGE_ROOT/optional/feishu/publish_podcast_files.py" "$TARGET_WORKSPACE/publish_podcast_files.py"; then
    mkdir -p "$WORKSPACE_BACKUP"
    cp -p "$TARGET_WORKSPACE/publish_podcast_files.py" "$WORKSPACE_BACKUP/publish_podcast_files.py"
  fi
  cp -p "$PACKAGE_ROOT/optional/feishu/publish_podcast_files.py" "$TARGET_WORKSPACE/publish_podcast_files.py"
  cp -p "$PACKAGE_ROOT/optional/feishu/README.md" "$TARGET_WORKSPACE/FEISHU_SETUP.md"
fi

chmod 755 "$TARGET_WORKSPACE"/*.py "$TARGET_SKILL/scripts"/*.py 2>/dev/null || true

if [[ $SKIP_RUNTIME -eq 0 ]]; then
  if [[ ! -x "$TARGET_WORKSPACE/.podcast-venv/bin/python" ]]; then
    "$PYTHON_CMD" -m venv "$TARGET_WORKSPACE/.podcast-venv"
  fi
  "$TARGET_WORKSPACE/.podcast-venv/bin/python" -m pip install --upgrade pip
  "$TARGET_WORKSPACE/.podcast-venv/bin/python" -m pip install -r "$TARGET_WORKSPACE/requirements-podcast.txt"
fi

VERIFY_ARGS=(--workspace "$TARGET_WORKSPACE" --codex-home "$TARGET_CODEX_HOME")
if [[ $SKIP_RUNTIME -eq 1 ]]; then
  VERIFY_ARGS+=(--allow-missing-runtime)
fi
"$PACKAGE_ROOT/scripts/verify_installation.py" "${VERIFY_ARGS[@]}"

print
print "播客工作流安装完成："
print "  工作区：$TARGET_WORKSPACE"
print "  Skill：$TARGET_SKILL"
if [[ $INCLUDE_FEISHU -eq 1 ]]; then
  print "  飞书辅助程序：已复制，但需要单独重新授权和配置桥接服务。"
fi
