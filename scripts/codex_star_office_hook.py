#!/usr/bin/env python3
"""Sync Codex hook events to Star Office UI.

This script is intentionally dependency-free so it can run from Codex hooks on
Windows, macOS, and Linux. It first tries the Star Office HTTP API, then falls
back to writing state.json directly.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_FILE = ROOT_DIR / "state.json"

VALID_STATES = {"idle", "writing", "researching", "executing", "syncing", "error"}

EVENT_STATE_MAP = {
    "SessionStart": ("syncing", "Codex 会话已启动，正在同步工作区"),
    "UserPromptSubmit": ("writing", "Codex 已收到新任务，开始处理"),
    "PermissionRequest": ("syncing", "Codex 正在等待授权确认"),
    "Stop": ("idle", "Codex 本轮任务已结束，待命中"),
}

TOOL_STATE_MAP = {
    "Bash": ("executing", "Codex 正在执行命令"),
    "shell_command": ("executing", "Codex 正在执行命令"),
    "apply_patch": ("writing", "Codex 正在修改文件"),
    "web": ("researching", "Codex 正在调研资料"),
    "browser": ("researching", "Codex 正在查看页面"),
}


def _read_payload() -> dict[str, Any]:
    if sys.stdin.isatty():
        return {}
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _event_name(payload: dict[str, Any]) -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    return str(payload.get("hook_event_name") or payload.get("event") or "")


def _tool_name(payload: dict[str, Any]) -> str:
    for key in ("tool_name", "tool", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("tool_name", "tool", "name"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _state_for_event(event: str, payload: dict[str, Any]) -> tuple[str, str]:
    if event in {"PreToolUse", "PostToolUse"}:
        tool = _tool_name(payload)
        state, detail = TOOL_STATE_MAP.get(tool, ("executing", "Codex 正在调用工具"))
        if event == "PostToolUse" and _looks_failed(payload):
            return "error", f"{tool or '工具'} 执行后需要检查"
        return state, detail if not tool else f"{detail}: {tool}"
    return EVENT_STATE_MAP.get(event, ("writing", f"Codex 状态更新: {event or 'unknown'}"))


def _looks_failed(payload: dict[str, Any]) -> bool:
    for key in ("exit_code", "status_code", "returncode"):
        value = payload.get(key)
        if isinstance(value, int) and value != 0:
            return True
    status = str(payload.get("status") or payload.get("result") or "").lower()
    return status in {"error", "failed", "failure"}


def _post_state(url: str, state: str, detail: str) -> bool:
    endpoint = url.rstrip("/") + "/set_state"
    body = json.dumps({"state": state, "detail": detail}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return 200 <= resp.status < 300
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False


def _write_state_file(path: Path, state: str, detail: str) -> bool:
    try:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.update(
            {
                "state": state,
                "detail": detail,
                "progress": data.get("progress", 0),
                "updated_at": datetime.now().isoformat(),
                "ttl_seconds": int(os.environ.get("STAR_OFFICE_CODEX_TTL", "300")),
            }
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def main() -> int:
    payload = _read_payload()
    event = _event_name(payload)
    state, detail = _state_for_event(event, payload)
    if state not in VALID_STATES:
        state = "writing"

    prefix = os.environ.get("STAR_OFFICE_CODEX_PREFIX", "").strip()
    if prefix:
        detail = f"{prefix}: {detail}"

    mode = os.environ.get("STAR_OFFICE_HOOK_MODE", "auto").strip().lower()
    office_url = os.environ.get("STAR_OFFICE_URL", "http://127.0.0.1:19000")
    state_file = Path(os.environ.get("STAR_OFFICE_STATE_FILE", str(DEFAULT_STATE_FILE)))

    ok = False
    if mode in {"auto", "http", "both"}:
        ok = _post_state(office_url, state, detail)
    if mode in {"auto", "file", "both"} and (not ok or mode in {"file", "both"}):
        ok = _write_state_file(state_file, state, detail) or ok

    print(f"star-office-codex: {state} - {detail} ({'ok' if ok else 'skipped'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
