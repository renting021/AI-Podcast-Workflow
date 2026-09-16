#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/scripts/install.sh" "$@"
result=$?
print
if [[ $result -eq 0 ]]; then
  print "安装完成。请重启 Codex，然后打开播客工作区。"
else
  print "安装未完成。请查看上面的错误说明。"
fi
print "按回车键关闭窗口。"
read -r
exit $result
