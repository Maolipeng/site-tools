from __future__ import annotations

import json
import re
import socket
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from sitectl.exceptions import StateError


PLACEHOLDER_PATTERN = re.compile(r"{{\s*(\w+)\s*}}")


def render_template(template_text: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        return str(context[key])

    return PLACEHOLDER_PATTERN.sub(replace, template_text)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise StateError(f"Invalid JSON in state file {path}: {exc}") from exc


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def format_host_for_url(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def backup_suffix(timestamp: str) -> str:
    normalized = timestamp.replace(":", "").replace("-", "")
    return f".bak.{normalized}"
