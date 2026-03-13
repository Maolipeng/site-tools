from __future__ import annotations

import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / "skills" / "sitectl-ops" / "scripts"


def load_script_module(script_name: str):
    module_path = SKILL_SCRIPTS / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{script_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load script: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillScriptsTestCase(unittest.TestCase):
    def test_site_json_emit_response_includes_trace_and_request_ids(self) -> None:
        site_json = load_script_module("site_json")
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = site_json._emit_response(
                "status",
                {"domain": "app.example.com"},
                ok=True,
                exit_code=0,
                trace_id="trace-123",
                request_id="request-456",
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["meta"]["command"], "status")
        self.assertEqual(payload["meta"]["mode"], "read")
        self.assertEqual(payload["meta"]["trace_id"], "trace-123")
        self.assertEqual(payload["meta"]["request_id"], "request-456")

    def test_site_fleet_autofix_filter_candidates_applies_domain_and_command_rules(self) -> None:
        site_fleet_autofix = load_script_module("site_fleet_autofix")
        candidates = [
            {
                "domain": "app.example.com",
                "command": "sitectl renew app.example.com",
                "priority": "medium",
                "reason": "certificate is expiring",
            },
            {
                "domain": "blocked.example.com",
                "command": "sitectl reload",
                "priority": "low",
                "reason": "safe reload candidate",
            },
        ]
        policy = {
            "allowed_commands": ["sitectl reload", "sitectl renew*"],
            "denied_domains": ["blocked.example.com"],
            "command_rules": {
                "sitectl renew*": {
                    "max_priority": "medium",
                    "require_dry_run": True,
                    "allowed_domains": ["*.example.com"],
                }
            },
        }
        selected, skipped, require_dry_run = site_fleet_autofix._filter_candidates(candidates, policy, "low")
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["command"], "sitectl renew app.example.com")
        self.assertEqual(selected[0]["matched_rule"], "sitectl renew*")
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["skip_reason"], "domain_denied")
        self.assertTrue(require_dry_run)

    def test_site_automation_templates_support_directives_and_json_meta(self) -> None:
        site_automation_templates = load_script_module("site_automation_templates")
        templates = site_automation_templates.build_templates()
        directive = site_automation_templates.render_directive(
            templates[0],
            str(REPO_ROOT),
            "suggested create",
        )
        self.assertIn("::automation-update{", directive)
        self.assertIn('mode="suggested create"', directive)
        self.assertIn(f'cwds="{REPO_ROOT}"', directive)

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = site_automation_templates.main(
                ["--trace-id", "trace-1", "--request-id", "request-1", "--format", "json", "--template", "daily-cert-warn"]
            )
        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["meta"]["trace_id"], "trace-1")
        self.assertEqual(payload["meta"]["request_id"], "request-1")
        self.assertEqual(len(payload["templates"]), 1)
        self.assertEqual(payload["templates"][0]["id"], "daily-cert-warn")


if __name__ == "__main__":
    unittest.main()
