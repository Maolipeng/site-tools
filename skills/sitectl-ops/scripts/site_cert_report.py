#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_PATH.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sitectl.cli import build_site_service  # noqa: E402
from sitectl.exceptions import SiteCtlError  # noqa: E402
from json_envelope import build_meta  # noqa: E402


def _to_jsonable(value: object) -> object:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _capture(func) -> dict[str, object]:
    try:
        return {"ok": True, "result": _to_jsonable(func())}
    except SiteCtlError as exc:
        return {"ok": False, "error": str(exc)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Return a batch certificate report for all managed sitectl sites.")
    parser.add_argument("--trace-id", help="Optional trace identifier to propagate into JSON output.")
    parser.add_argument("--request-id", help="Optional request identifier to propagate into JSON output.")
    parser.add_argument("--days", type=int, default=30, help="Warning threshold in days.")
    parser.add_argument("--skip-verify", action="store_true", help="Skip certificate/private key match verification.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    site_service = build_site_service()

    records = []
    warnings = 0
    for site in site_service.list_sites():
        cert_info = _capture(lambda domain=site.domain: site_service.get_certificate_info(domain))
        cert_verify = None if args.skip_verify else _capture(lambda domain=site.domain: site_service.verify_certificate(domain))

        warning_reasons: list[str] = []
        if cert_info["ok"]:
            cert_result = cert_info["result"]
            days_remaining = cert_result.get("days_remaining")
            if not cert_result.get("exists"):
                warning_reasons.append("certificate_missing")
            elif days_remaining is not None and days_remaining <= args.days:
                warning_reasons.append(f"expires_in_{days_remaining}_days")
        else:
            warning_reasons.append("cert_info_failed")

        if cert_verify is not None:
            if not cert_verify["ok"]:
                warning_reasons.append("cert_verify_failed")
            elif not cert_verify["result"].get("matches"):
                warning_reasons.append("cert_key_mismatch")

        if warning_reasons:
            warnings += 1

        records.append(
            {
                "domain": site.domain,
                "type": site.type,
                "warning_reasons": warning_reasons,
                "cert_info": cert_info,
                "cert_verify": cert_verify,
            }
        )

    report = {
        "ok": warnings == 0,
        "meta": build_meta(
            "site-cert-report",
            "report",
            0 if warnings == 0 else 1,
            trace_id=args.trace_id,
            request_id=args.request_id,
        ),
        "days": args.days,
        "summary": {
            "sites_total": len(records),
            "sites_with_warnings": warnings,
        },
        "results": records,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if warnings == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
