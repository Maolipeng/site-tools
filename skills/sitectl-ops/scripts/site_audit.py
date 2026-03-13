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


def _capture(label: str, func) -> dict[str, object]:
    try:
        return {"ok": True, "result": _to_jsonable(func())}
    except SiteCtlError as exc:
        return {"ok": False, "error": str(exc), "source": label}


def _append_once(items: list[dict[str, str]], command: str, priority: str, reason: str) -> None:
    if any(item["command"] == command for item in items):
        return
    items.append({"command": command, "priority": priority, "reason": reason})


def _build_summary(
    domain: str,
    checks: dict[str, object],
) -> tuple[str, str, str, list[str], list[dict[str, str]], list[dict[str, str]]]:
    issues: list[str] = []
    recommendations: list[dict[str, str]] = []
    autofix_candidates: list[dict[str, str]] = []

    status_check = checks["status"]
    if not status_check["ok"]:
        issues.append(f"status lookup failed: {status_check['error']}")
        _append_once(recommendations, f"sitectl status {domain}", "high", "status lookup failed")
    else:
        status_result = status_check["result"]
        if not status_result.get("config_exists"):
            issues.append("nginx config is missing")
            _append_once(recommendations, f"sitectl status {domain}", "high", "confirm missing nginx config")
        if not status_result.get("enabled_exists"):
            issues.append("nginx enabled symlink is missing")
            _append_once(recommendations, "sitectl reload --dry-run", "medium", "preview nginx reload path")
        if not status_result.get("cert_exists"):
            issues.append("certificate files are missing")
            _append_once(recommendations, f"sitectl cert-info {domain}", "high", "inspect missing certificate files")
        if not status_result.get("port_open"):
            issues.append("local service port is not reachable")
            _append_once(recommendations, f"sitectl logs {domain} --error --lines 200", "high", "inspect nginx error log for local port failure")
        if status_result.get("type") == "node" and status_result.get("pm2_exists") is False:
            issues.append("pm2 process is not running")
            _append_once(recommendations, f"sitectl logs {domain} --pm2 --lines 200", "high", "inspect PM2 logs")
        if status_result.get("type") == "systemd" and status_result.get("systemd_active") is False:
            issues.append("systemd service is not active")
            _append_once(recommendations, f"sitectl logs {domain} --systemd --lines 200", "high", "inspect systemd service logs")
        if (
            status_result.get("config_exists")
            and status_result.get("enabled_exists")
            and status_result.get("cert_exists")
            and status_result.get("port_open")
        ):
            autofix_candidates.append(
                {
                    "command": "sitectl reload",
                    "priority": "low",
                    "reason": "site basics look healthy enough for a safe nginx reload",
                }
            )

    cert_info = checks["cert_info"]
    if cert_info["ok"]:
        cert_result = cert_info["result"]
        days_remaining = cert_result.get("days_remaining")
        if cert_result.get("exists") and days_remaining is not None and days_remaining <= 14:
            issues.append(f"certificate expires soon: {days_remaining} day(s) remaining")
            _append_once(recommendations, "sitectl cert-warn --days 14", "medium", "review expiring certificates")
            if cert_result.get("ssl_mode") == "letsencrypt":
                autofix_candidates.append(
                    {
                        "command": f"sitectl renew {domain}",
                        "priority": "medium",
                        "reason": "letsencrypt certificate is nearing expiry",
                    }
                )

    cert_verify = checks["cert_verify"]
    if not cert_verify["ok"]:
        issues.append(f"certificate verification failed: {cert_verify['error']}")
        _append_once(recommendations, f"sitectl cert-verify {domain}", "high", "rerun certificate verification")
    else:
        verify_result = cert_verify["result"]
        if not verify_result.get("matches"):
            issues.append("certificate and private key do not match")
            _append_once(recommendations, f"sitectl cert-verify {domain}", "critical", "certificate and key mismatch")

    healthcheck = checks["healthcheck"]
    if not healthcheck["ok"]:
        issues.append(f"healthcheck failed to run: {healthcheck['error']}")
        _append_once(recommendations, f"sitectl healthcheck {domain}", "high", "rerun healthcheck directly")
    else:
        failed_probes = [probe["name"] for probe in healthcheck["result"].get("probes", []) if not probe.get("ok")]
        if failed_probes:
            issues.append(f"healthcheck probes failed: {', '.join(failed_probes)}")
            _append_once(recommendations, f"sitectl healthcheck {domain}", "high", "reproduce failed healthcheck probes")
            _append_once(recommendations, f"sitectl logs {domain} --error --lines 200", "high", "inspect nginx error log after failed probes")

    error_log = checks["error_log"]
    if not error_log["ok"]:
        issues.append(f"error log unavailable: {error_log['error']}")
        _append_once(recommendations, f"sitectl logs {domain} --error --lines 200", "medium", "retry fetching error logs")

    runtime_log = checks.get("runtime_log")
    if runtime_log is not None and not runtime_log["ok"]:
        issues.append(f"runtime log unavailable: {runtime_log['error']}")

    if not issues:
        summary = "healthy"
        severity = "info"
        next_step_priority = "none"
    elif len(issues) <= 2:
        summary = "degraded"
        severity = "warning"
        next_step_priority = "medium"
    else:
        summary = "unhealthy"
        severity = "critical"
        next_step_priority = "high"
    if any("do not match" in issue for issue in issues):
        severity = "critical"
        next_step_priority = "high"
    return summary, severity, next_step_priority, issues, recommendations, autofix_candidates


def build_audit_report(
    site_service,
    domain: str,
    *,
    path: str = "/",
    timeout: float = 5.0,
    error_lines: int = 100,
    include_runtime_log: bool = False,
    runtime_lines: int = 100,
) -> dict[str, object]:
    status_info = _capture("status", lambda: site_service.get_status(domain))
    cert_info = _capture("cert-info", lambda: site_service.get_certificate_info(domain))
    cert_verify = _capture("cert-verify", lambda: site_service.verify_certificate(domain))
    healthcheck = _capture(
        "healthcheck",
        lambda: site_service.run_healthcheck(domain, path=path, timeout=timeout),
    )
    error_log = _capture("logs:error", lambda: site_service.get_logs(domain, "error", lines=error_lines))

    runtime_log: dict[str, object] | None = None
    if include_runtime_log and status_info.get("ok") and isinstance(status_info.get("result"), dict):
        status_result = status_info["result"]
        runtime_kind = None
        if status_result.get("type") == "node" and status_result.get("pm2_exists"):
            runtime_kind = "pm2"
        elif status_result.get("type") == "systemd" and status_result.get("systemd_active"):
            runtime_kind = "systemd"
        if runtime_kind:
            runtime_log = _capture(
                f"logs:{runtime_kind}",
                lambda: site_service.get_logs(domain, runtime_kind, lines=runtime_lines),
            )

    summary, severity, next_step_priority, issues, recommendations, autofix_candidates = _build_summary(
        domain,
        {
            "status": status_info,
            "cert_info": cert_info,
            "cert_verify": cert_verify,
            "healthcheck": healthcheck,
            "error_log": error_log,
            "runtime_log": runtime_log,
        },
    )
    healthy = summary == "healthy"
    return {
        "ok": healthy,
        "domain": domain,
        "summary": summary,
        "severity": severity,
        "next_step_priority": next_step_priority,
        "issues": issues,
        "recommended_actions": recommendations,
        "autofix_candidates": autofix_candidates,
        "checks": {
            "status": status_info,
            "cert_info": cert_info,
            "cert_verify": cert_verify,
            "healthcheck": healthcheck,
            "error_log": error_log,
            "runtime_log": runtime_log,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Return a structured sitectl audit report for one site.")
    parser.add_argument("--trace-id", help="Optional trace identifier to propagate into JSON output.")
    parser.add_argument("--request-id", help="Optional request identifier to propagate into JSON output.")
    parser.add_argument("domain")
    parser.add_argument("--path", default="/", help="Healthcheck path.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Healthcheck timeout in seconds.")
    parser.add_argument("--error-lines", type=int, default=100, help="Tail this many error log lines.")
    parser.add_argument("--include-runtime-log", action="store_true", help="Include pm2/systemd logs when configured.")
    parser.add_argument("--runtime-lines", type=int, default=100, help="Tail this many runtime log lines.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    site_service = build_site_service()
    report = build_audit_report(
        site_service,
        args.domain,
        path=args.path,
        timeout=args.timeout,
        error_lines=args.error_lines,
        include_runtime_log=args.include_runtime_log,
        runtime_lines=args.runtime_lines,
    )
    report["meta"] = build_meta(
        "site-audit",
        "audit",
        0 if report["ok"] else 1,
        trace_id=args.trace_id,
        request_id=args.request_id,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
