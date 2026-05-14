# Codex Integration

这份定制让 Codex 可以通过 hooks 把自己的工作状态同步到 Star Office UI。

## 工作方式

仓库内置了：

- `.codex/config.toml`：启用 Codex hooks。
- `.codex/hooks.json`：把 Codex 生命周期事件接到同步脚本。
- `scripts/codex_star_office_hook.py`：接收 hook 事件，更新 Star Office 状态。

默认行为是：

1. 优先请求 `STAR_OFFICE_URL/set_state`，默认地址是 `http://127.0.0.1:19000/set_state`。
2. 如果本地后端还没启动，请求失败时会回退写入仓库根目录的 `state.json`。

## 状态映射

| Codex 事件 | Star Office 状态 | 含义 |
| --- | --- | --- |
| `SessionStart` | `syncing` | 会话启动或恢复 |
| `UserPromptSubmit` | `writing` | 收到新任务 |
| `PreToolUse` | `executing` / `writing` / `researching` | 正在调用工具 |
| `PostToolUse` | `error`（失败时） | 工具结果需要检查 |
| `PermissionRequest` | `syncing` | 等待授权 |
| `Stop` | `idle` | 本轮结束，回到待命 |

## 本地使用

先启动 Star Office：

```powershell
Copy-Item state.sample.json state.json
python -m pip install -r backend/requirements.txt
python backend/app.py
```

打开：

```text
http://127.0.0.1:19000
```

然后在这个仓库里开启新的 Codex 会话。Codex 读取本仓库 `.codex/` 配置后，就会自动同步状态。

## 可选环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `STAR_OFFICE_URL` | `http://127.0.0.1:19000` | Star Office 后端地址 |
| `STAR_OFFICE_STATE_FILE` | `<repo>/state.json` | HTTP 不可用时写入的状态文件 |
| `STAR_OFFICE_HOOK_MODE` | `auto` | `auto` / `http` / `file` / `both` |
| `STAR_OFFICE_CODEX_PREFIX` | 空 | 给状态文案加前缀，例如 `Codex` |
| `STAR_OFFICE_CODEX_TTL` | `300` | 写入 `state.json` 的工作态过期秒数 |

## 安全说明

这套 hooks 只向本机 Star Office 后端写状态，或写入本仓库 `state.json`。脚本不会读取 Codex 登录凭据，也不会上传 prompt、源码或仓库内容。
