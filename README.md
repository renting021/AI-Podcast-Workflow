# Codex 播客工作流迁移包

版本：1.0.0  
目标环境：Apple 芯片 Mac、macOS、Codex 桌面端

这个包只包含可复用工作流、项目模板、程序和自定义 Skill。它不包含历史播客、音频、转录、飞书数据库、日志、用户或群标识、App Secret、Token、钥匙串内容和模型缓存。

## 最简单的安装方式

1. 把整个压缩包复制到新电脑并解压。
2. 双击 `安装播客工作流.command`。
3. 安装结束后重启 Codex，打开 `~/Documents/Codex podcast Product`。
4. 在 Codex 中发送一条测试任务：`请检查播客工作流是否安装完整。`

安装程序默认执行以下操作：

- 把工作流复制到 `~/Documents/Codex podcast Product`；
- 把 `refine-podcast-dialogue` 安装到 `${CODEX_HOME:-~/.codex}/skills`；
- 在工作区创建独立的 `.podcast-venv`；
- 安装经过当前机器验证的 `mlx-whisper==0.4.3`；
- 运行语法、Skill 结构、转录检查器和对话一致性检查器测试。

安装程序不会覆盖内容不同的同名文件。需要更新已有安装时，在终端中使用：

```bash
./scripts/install.sh --force
```

旧文件会先保存到目标目录的 `.migration-backups/`，再执行更新。

## 系统要求

- Apple 芯片 Mac（`arm64`）；
- Python 3.10–3.13，推荐并已验证 Python 3.12；
- FFmpeg 与 FFprobe；
- 网络连接，用于首次安装 Python 依赖和首次下载 Whisper 模型。

如果已经安装 Homebrew，但缺少 Python 或 FFmpeg，可以显式允许安装程序补齐：

```bash
./scripts/install.sh --install-system-deps
```

该选项会调用 Homebrew 安装 `python@3.12` 和/或 `ffmpeg`。

如果电脑上已有兼容 Python，但命令名不在默认搜索路径中，可直接指定解释器：

```bash
./scripts/install.sh --python "/完整路径/python3.12"
```

安装器会拒绝 Python 3.14 及更高版本，因为当前依赖组合尚未在这些版本上验证。

## 自定义安装位置

```bash
./scripts/install.sh \
  --workspace "/你的路径/Codex podcast Product" \
  --codex-home "/你的路径/.codex"
```

## 飞书发布

飞书属于可选的外部系统。迁移包不会携带任何飞书凭据，也不会默认安装或启动桥接服务。

需要把群附件发布程序一并放入工作区时使用：

```bash
./scripts/install.sh --include-feishu-tools
```

随后按照 `optional/feishu/README.md` 在新电脑重新安装飞书桥、设置白名单并写入钥匙串。不要从旧电脑复制钥匙串、SQLite 数据库或日志。

## 验证与故障定位

双击 `验证播客工作流.command`，或执行：

```bash
./scripts/verify_installation.py
```

验证通过仅说明本地程序与 Skill 可用。完整验收还应选一段 1–3 分钟的公开音频，实际执行下载、转录、文章合并和对话一致性检查。

如果在无图形设备的后台、沙盒或虚拟化会话中运行，`metal_runtime` 可能显示为跳过；这表示 MLX Whisper 已安装，但当前进程拿不到 Metal GPU。请在普通 macOS 终端中再次运行验证，或直接执行短音频验收。

## 包含内容

- `workspace/`：`AGENTS.md`、工作流规则、质检清单、项目模板和处理程序；
- `skills/refine-podcast-dialogue/`：对话体写作与跨分段漂移检查 Skill；
- `scripts/`：安全安装与验收程序；
- `optional/feishu/`：不含凭据的飞书发布辅助文件；
- `manifest.json` 与 `SHA256SUMS`：版本信息和文件完整性校验。
