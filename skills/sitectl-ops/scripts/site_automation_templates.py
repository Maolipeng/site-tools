#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_PATH.parents[3]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from json_envelope import build_meta

SKILL_SCRIPTS = REPO_ROOT / "skills" / "sitectl-ops" / "scripts"


def build_templates() -> list[dict[str, object]]:
    return [
        {
            "id": "daily-fleet-audit",
            "name": "Daily Fleet Audit",
            "goal": "Run a full sitectl fleet audit once per day and report unhealthy or degraded sites.",
            "command": f"python3 {SKILL_SCRIPTS / 'site_fleet_audit.py'} --include-runtime-log --only-problems",
            "recommended_schedule": "Daily at 09:00 local time",
            "rrule": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=9;BYMINUTE=0",
            "status": "ACTIVE",
            "automation_prompt": "Run the sitectl fleet audit, summarize degraded and unhealthy sites, list global recommendations, and highlight any global autofix candidates.",
        },
        {
            "id": "daily-cert-warn",
            "name": "Daily Certificate Warning",
            "goal": "Detect missing or soon-to-expire certificates and surface alerts.",
            "command": f"python3 {SKILL_SCRIPTS / 'site_json.py'} cert-warn --days 14",
            "recommended_schedule": "Daily at 08:30 local time",
            "rrule": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=8;BYMINUTE=30",
            "status": "ACTIVE",
            "automation_prompt": "Run the sitectl certificate warning check and summarize any missing or expiring certificates within 14 days.",
        },
        {
            "id": "weekly-cert-report",
            "name": "Weekly Certificate Report",
            "goal": "Review certificate posture across all managed sites.",
            "command": f"python3 {SKILL_SCRIPTS / 'site_cert_report.py'} --days 30",
            "recommended_schedule": "Weekly on Monday at 10:00 local time",
            "rrule": "FREQ=WEEKLY;BYDAY=MO;BYHOUR=10;BYMINUTE=0",
            "status": "ACTIVE",
            "automation_prompt": "Generate the sitectl weekly certificate report and summarize expiring, missing, or mismatched certificates.",
        },
        {
            "id": "preview-autofix",
            "name": "Preview Fleet Autofix",
            "goal": "Preview safe autofix candidates without making changes.",
            "command": f"python3 {SKILL_SCRIPTS / 'site_fleet_autofix.py'} --only-problems --max-priority medium",
            "recommended_schedule": "Daily at 09:15 local time",
            "rrule": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=9;BYMINUTE=15",
            "status": "ACTIVE",
            "automation_prompt": "Preview sitectl fleet autofix candidates, summarize the selected commands, and do not apply changes.",
        },
    ]


def _select_templates(templates: list[dict[str, object]], template_ids: list[str] | None) -> list[dict[str, object]]:
    if not template_ids:
        return templates
    allowed = set(template_ids)
    return [item for item in templates if item["id"] in allowed]


def _escape_directive_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def render_directive(template: dict[str, object], cwd: str, mode: str) -> str:
    return (
        "::automation-update{"
        f"mode=\"{_escape_directive_value(mode)}\" "
        f"name=\"{_escape_directive_value(str(template['name']))}\" "
        f"prompt=\"{_escape_directive_value(str(template['automation_prompt']))}\" "
        f"rrule=\"{_escape_directive_value(str(template['rrule']))}\" "
        f"cwds=\"{_escape_directive_value(cwd)}\" "
        f"status=\"{_escape_directive_value(str(template['status']))}\""
        "}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print reusable automation templates for sitectl-ops.")
    parser.add_argument("--trace-id", help="Optional trace identifier to propagate into JSON output.")
    parser.add_argument("--request-id", help="Optional request identifier to propagate into JSON output.")
    parser.add_argument("--format", choices=["json", "markdown", "directives"], default="json")
    parser.add_argument("--template", action="append", help="Limit output to one or more template ids.")
    parser.add_argument("--cwd", default=str(REPO_ROOT), help="Workspace path used in directive output.")
    parser.add_argument(
        "--directive-mode",
        choices=["suggested create", "suggested update"],
        default="suggested create",
        help="Directive mode used when --format directives is selected.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    templates = _select_templates(build_templates(), args.template)

    if args.format == "markdown":
        for item in templates:
            print(f"## {item['name']}")
            print(f"- id: {item['id']}")
            print(f"- goal: {item['goal']}")
            print(f"- command: `{item['command']}`")
            print(f"- recommended_schedule: {item['recommended_schedule']}")
            print(f"- rrule: {item['rrule']}")
            print(f"- automation_prompt: {item['automation_prompt']}")
            print()
        return 0

    if args.format == "directives":
        for item in templates:
            print(render_directive(item, args.cwd, args.directive_mode))
        return 0

    print(
        json.dumps(
            {
                "meta": build_meta(
                    "site-automation-templates",
                    "read",
                    0,
                    trace_id=args.trace_id,
                    request_id=args.request_id,
                ),
                "templates": templates,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
