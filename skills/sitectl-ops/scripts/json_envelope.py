from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone


def resolve_trace_id(value: str | None = None) -> str:
    return value or os.environ.get("SITECTL_TRACE_ID") or str(uuid.uuid4())


def resolve_request_id(value: str | None = None) -> str:
    return value or os.environ.get("SITECTL_REQUEST_ID") or str(uuid.uuid4())


def build_meta(
    command: str,
    mode: str,
    exit_code: int,
    *,
    trace_id: str | None = None,
    request_id: str | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    meta: dict[str, object] = {
        "command": command,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": exit_code,
        "trace_id": resolve_trace_id(trace_id),
        "request_id": resolve_request_id(request_id),
    }
    if extra:
        meta.update({key: value for key, value in extra.items() if value is not None})
    return meta


def print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
