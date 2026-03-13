#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
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
from sitectl.exceptions import SiteCtlError  # noqa: E402
from json_envelope import build_meta  # noqa: E402
from site_fleet_audit import _dedupe_actions  # noqa: E402
from site_audit import build_audit_report  # noqa: E402


PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DEFAULT_POLICY_PATH = SCRIPT_DIR.parent / "assets" / "autofix-policy.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preview or execute fleet autofix candidates derived from sitectl audits.")
    parser.add_argument("--trace-id", help="Optional trace identifier to propagate into JSON output.")
    parser.add_argument("--request-id", help="Optional request identifier to propagate into JSON output.")
    parser.add_argument("--domain", action="append", help="Limit autofix to one or more exact domains.")
    parser.add_argument("--match", help="Limit autofix to domains containing this substring.")
    parser.add_argument("--only-problems", action="store_true", help="Only consider degraded or unhealthy sites.")
    parser.add_argument("--max-priority", choices=["critical", "high", "medium", "low"])
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_PATH), help="Path to an autofix policy JSON file.")
    parser.add_argument("--apply", action="store_true", help="Execute supported autofix commands. Defaults to preview only.")
    parser.add_argument("--dry-run-before-apply", action="store_true", help="Run structured dry-run previews before applying supported fixes.")
    parser.add_argument("--path", default="/", help="Healthcheck path for audit generation.")
    parser.add_argument("--timeout", type=float, default=5.0, help="Healthcheck timeout in seconds.")
    parser.add_argument("--error-lines", type=int, default=100, help="Tail this many error log lines.")
    parser.add_argument("--include-runtime-log", action="store_true", help="Include runtime logs while building audits.")
    parser.add_argument("--runtime-lines", type=int, default=100, help="Tail this many runtime log lines.")
    return parser


def _load_policy(path: str) -> dict[str, object]:
    policy_path = Path(path)
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid autofix policy: {path}")
    return payload


def _is_allowed(command: str, allowed_commands: list[str]) -> bool:
    return any(fnmatch.fnmatch(command, pattern) for pattern in allowed_commands)


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def _resolve_command_rule(command: str, command_rules: dict[str, object]) -> tuple[str | None, dict[str, object]]:
    for pattern, rule in command_rules.items():
        if fnmatch.fnmatch(command, pattern) and isinstance(rule, dict):
            return pattern, rule
    return None, {}


def _filter_candidates(
    candidates: list[dict[str, str]],
    policy: dict[str, object],
    max_priority: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]], bool]:
    allowed_commands = [str(item) for item in policy.get("allowed_commands", [])]
    denied_commands = [str(item) for item in policy.get("denied_commands", [])]
    allowed_domains = [str(item) for item in policy.get("allowed_domains", [])]
    denied_domains = [str(item) for item in policy.get("denied_domains", [])]
    command_rules = policy.get("command_rules", {})
    if not isinstance(command_rules, dict):
        command_rules = {}

    max_order = PRIORITY_ORDER[max_priority]
    selected: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    require_dry_run = bool(policy.get("require_dry_run_before_apply"))

    for candidate in candidates:
        command = str(candidate["command"])
        domain = str(candidate.get("domain", ""))
        priority = str(candidate.get("priority", "low"))
        priority_order = PRIORITY_ORDER.get(priority, 99)
        if priority_order > max_order:
            skipped.append({**candidate, "skip_reason": "priority_exceeds_threshold"})
            continue
        if denied_commands and _matches_any(command, denied_commands):
            skipped.append({**candidate, "skip_reason": "command_denied"})
            continue
        if allowed_commands and not _is_allowed(command, allowed_commands):
            skipped.append({**candidate, "skip_reason": "command_not_allowlisted"})
            continue
        if denied_domains and _matches_any(domain, denied_domains):
            skipped.append({**candidate, "skip_reason": "domain_denied"})
            continue
        if allowed_domains and not _matches_any(domain, allowed_domains):
            skipped.append({**candidate, "skip_reason": "domain_not_allowlisted"})
            continue

        rule_pattern, rule = _resolve_command_rule(command, command_rules)
        if rule:
            rule_max_priority = rule.get("max_priority")
            if isinstance(rule_max_priority, str):
                rule_order = PRIORITY_ORDER.get(rule_max_priority, 99)
                if priority_order > rule_order:
                    skipped.append(
                        {
                            **candidate,
                            "skip_reason": "command_rule_priority_exceeded",
                            "matched_rule": rule_pattern or "",
                        }
                    )
                    continue
            rule_denied_domains = [str(item) for item in rule.get("denied_domains", [])]
            if rule_denied_domains and _matches_any(domain, rule_denied_domains):
                skipped.append({**candidate, "skip_reason": "command_rule_domain_denied", "matched_rule": rule_pattern or ""})
                continue
            rule_allowed_domains = [str(item) for item in rule.get("allowed_domains", [])]
            if rule_allowed_domains and not _matches_any(domain, rule_allowed_domains):
                skipped.append(
                    {
                        **candidate,
                        "skip_reason": "command_rule_domain_not_allowlisted",
                        "matched_rule": rule_pattern or "",
                    }
                )
                continue
            if rule.get("require_dry_run"):
                require_dry_run = True
        selected.append({**candidate, "matched_rule": rule_pattern or ""})

    return selected, skipped, require_dry_run


def _preview_candidate(site_service, action: dict[str, str]) -> dict[str, object]:
    command = action["command"]
    try:
        if command == "sitectl reload":
            result = site_service.reload_nginx(dry_run=True)
        elif command.startswith("sitectl renew "):
            result = site_service.renew_certificates(command.removeprefix("sitectl renew ").strip(), dry_run=True)
        elif command == "sitectl renew":
            result = site_service.renew_certificates(None, dry_run=True)
        else:
            return {
                "command": command,
                "previewed": False,
                "status": "unsupported",
                "reason": "no structured dry-run executor for this autofix candidate",
            }
    except SiteCtlError as exc:
        return {
            "command": command,
            "previewed": True,
            "status": "failed",
            "error": str(exc),
        }
    return {
        "command": command,
        "previewed": True,
        "status": "ok",
        "result": result,
    }


def _execute_candidate(site_service, action: dict[str, str]) -> dict[str, object]:
    command = action["command"]
    try:
        if command == "sitectl reload":
            result = site_service.reload_nginx(dry_run=False)
        elif command.startswith("sitectl renew "):
            result = site_service.renew_certificates(command.removeprefix("sitectl renew ").strip(), dry_run=False)
        elif command == "sitectl renew":
            result = site_service.renew_certificates(None, dry_run=False)
        else:
            return {
                "command": command,
                "executed": False,
                "status": "unsupported",
                "reason": "no structured executor for this autofix candidate",
            }
    except SiteCtlError as exc:
        return {
            "command": command,
            "executed": True,
            "status": "failed",
            "error": str(exc),
        }
    return {
        "command": command,
        "executed": True,
        "status": "ok",
        "result": result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    site_service = build_site_service()
    policy = _load_policy(args.policy)
    if not args.max_priority and policy.get("default_max_priority"):
        args.max_priority = str(policy["default_max_priority"])
    if not args.max_priority:
        args.max_priority = "medium"

    sites = site_service.list_sites()
    if args.domain:
        allowed = {item.lower() for item in args.domain}
        sites = [site for site in sites if site.domain.lower() in allowed]
    if args.match:
        needle = args.match.lower()
        sites = [site for site in sites if needle in site.domain.lower()]

    audits = [
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
        audits = [item for item in audits if item["summary"] != "healthy"]

    candidates = _dedupe_actions(audits, "autofix_candidates")
    candidates, skipped_candidates, policy_requires_dry_run = _filter_candidates(candidates, policy, args.max_priority)
    effective_dry_run_before_apply = args.dry_run_before_apply or policy_requires_dry_run

    execution_results: list[dict[str, object]] = []
    preview_results: list[dict[str, object]] = []
    if args.apply:
        if effective_dry_run_before_apply:
            for candidate in candidates:
                preview_results.append(_preview_candidate(site_service, candidate))
            supported_preview_failures = [
                item for item in preview_results if item.get("previewed") and item.get("status") == "failed"
            ]
            if supported_preview_failures:
                report = {
                    "ok": False,
                    "meta": build_meta(
                        "site-fleet-autofix",
                        "apply",
                        1,
                        trace_id=args.trace_id,
                        request_id=args.request_id,
                    ),
                    "mode": "apply",
                    "dry_run_before_apply": True,
                    "max_priority": args.max_priority,
                    "policy_path": str(Path(args.policy).resolve()),
                    "effective_policy": {
                        "allowed_commands": [str(item) for item in policy.get("allowed_commands", [])],
                        "denied_commands": [str(item) for item in policy.get("denied_commands", [])],
                        "allowed_domains": [str(item) for item in policy.get("allowed_domains", [])],
                        "denied_domains": [str(item) for item in policy.get("denied_domains", [])],
                        "default_max_priority": policy.get("default_max_priority"),
                        "require_dry_run_before_apply": bool(policy.get("require_dry_run_before_apply")),
                        "command_rules": policy.get("command_rules", {}),
                    },
                    "selected_candidates": candidates,
                    "skipped_candidates": skipped_candidates,
                    "preview_results": preview_results,
                    "execution_results": execution_results,
                }
                print(json.dumps(report, indent=2, ensure_ascii=False))
                return 1
        for candidate in candidates:
            execution_results.append(_execute_candidate(site_service, candidate))

    report = {
        "ok": all(item.get("status") in {"ok", "unsupported"} for item in execution_results) if args.apply else True,
        "meta": build_meta(
            "site-fleet-autofix",
            "apply" if args.apply else "preview",
            0,
            trace_id=args.trace_id,
            request_id=args.request_id,
        ),
        "mode": "apply" if args.apply else "preview",
        "dry_run_before_apply": effective_dry_run_before_apply,
        "max_priority": args.max_priority,
        "policy_path": str(Path(args.policy).resolve()),
        "effective_policy": {
            "allowed_commands": [str(item) for item in policy.get("allowed_commands", [])],
            "denied_commands": [str(item) for item in policy.get("denied_commands", [])],
            "allowed_domains": [str(item) for item in policy.get("allowed_domains", [])],
            "denied_domains": [str(item) for item in policy.get("denied_domains", [])],
            "default_max_priority": policy.get("default_max_priority"),
            "require_dry_run_before_apply": bool(policy.get("require_dry_run_before_apply")),
            "command_rules": policy.get("command_rules", {}),
        },
        "selected_candidates": candidates,
        "skipped_candidates": skipped_candidates,
        "preview_results": preview_results,
        "execution_results": execution_results,
    }
    report["meta"]["exit_code"] = 0 if report["ok"] else 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
