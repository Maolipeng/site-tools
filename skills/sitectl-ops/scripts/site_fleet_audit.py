#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_PATH.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sitectl.cli import build_site_service  # noqa: E402
from json_envelope import build_meta  # noqa: E402
from site_audit import build_audit_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Return a structured audit report for all managed sitectl sites.")
    parser.add_argument("--trace-id", help="Optional trace identifier to propagate into JSON output.")
    parser.add_argument("--request-id", help="Optional request identifier to propagate into JSON output.")
    parser.add_argument("--domain", action="append", help="Limit audit to one or more exact domains.")
    parser.add_argument("--match", help="Limit audit to domains containing this substring.")
    parser.add_argument("--only-problems", action="store_true", help="Only include degraded or unhealthy sites in results.")
    parser.add_argument("--path", default="/", help="Healthcheck path.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Healthcheck timeout in seconds.")
    parser.add_argument("--error-lines", type=int, default=100, help="Tail this many error log lines.")
    parser.add_argument("--include-runtime-log", action="store_true", help="Include pm2/systemd logs when configured.")
    parser.add_argument("--runtime-lines", type=int, default=100, help="Tail this many runtime log lines.")
    return parser


def _dedupe_actions(results: list[dict[str, object]], field: str) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, str]] = []
    for result in results:
        for action in result.get(field, []):
            key = (str(action.get("command")), str(action.get("reason")))
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "domain": str(result.get("domain")),
                    "command": str(action.get("command")),
                    "priority": str(action.get("priority")),
                    "reason": str(action.get("reason")),
                }
            )
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(merged, key=lambda item: (priority_order.get(item["priority"], 9), item["domain"], item["command"]))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    site_service = build_site_service()

    sites = site_service.list_sites()
    if args.domain:
        allowed = {item.lower() for item in args.domain}
        sites = [site for site in sites if site.domain.lower() in allowed]
    if args.match:
        needle = args.match.lower()
        sites = [site for site in sites if needle in site.domain.lower()]
    results = [
        build_audit_report(
            site_service,
            site.domain,
            path=args.path,
            timeout=args.timeout,
            error_lines=args.error_lines,
            include_runtime_log=args.include_runtime_log,
            runtime_lines=args.runtime_lines,
        )
        for site in sites
    ]
    if args.only_problems:
        results = [item for item in results if item["summary"] != "healthy"]

    summary = {
        "sites_total": len(results),
        "healthy": sum(1 for item in results if item["summary"] == "healthy"),
        "degraded": sum(1 for item in results if item["summary"] == "degraded"),
        "unhealthy": sum(1 for item in results if item["summary"] == "unhealthy"),
        "critical": sum(1 for item in results if item["severity"] == "critical"),
        "next_step_high": sum(1 for item in results if item["next_step_priority"] == "high"),
        "next_step_medium": sum(1 for item in results if item["next_step_priority"] == "medium"),
    }
    global_recommendations = _dedupe_actions(results, "recommended_actions")
    global_autofix_candidates = _dedupe_actions(results, "autofix_candidates")
    report = {
        "ok": summary["degraded"] == 0 and summary["unhealthy"] == 0,
        "meta": build_meta(
            "site-fleet-audit",
            "audit",
            0 if summary["degraded"] == 0 and summary["unhealthy"] == 0 else 1,
            trace_id=args.trace_id,
            request_id=args.request_id,
        ),
        "summary": summary,
        "global_recommendations": global_recommendations,
        "global_autofix_candidates": global_autofix_candidates,
        "results": results,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
