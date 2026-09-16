#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/scripts/verify_installation.py" "$@"
result=$?
print
print "按回车键关闭窗口。"
read -r
exit $result
