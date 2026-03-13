# Automation

Use this reference when the user wants recurring sitectl checks or a scheduled automation.

## Recommended recurring jobs

### Daily fleet audit

Purpose:

- Run a full-site audit once per day
- Catch unhealthy or degraded sites early
- Surface global recommendations and autofix candidates

Suggested task:

```bash
python3 /path/to/site-tools/skills/sitectl-ops/scripts/site_fleet_audit.py --include-runtime-log
```

Directive helper:

```bash
python3 /path/to/site-tools/skills/sitectl-ops/scripts/site_automation_templates.py --format directives --template daily-fleet-audit
```

### Daily certificate warning check

Purpose:

- Detect missing or expiring certificates
- Return non-zero when warnings exist

Suggested task:

```bash
python3 /path/to/site-tools/skills/sitectl-ops/scripts/site_json.py cert-warn --days 14
```

Directive helper:

```bash
python3 /path/to/site-tools/skills/sitectl-ops/scripts/site_automation_templates.py --format directives --template daily-cert-warn
```

### Weekly certificate report

Purpose:

- Review every managed site's certificate posture
- Spot mismatches and expiring certs in one report

Suggested task:

```bash
python3 /path/to/site-tools/skills/sitectl-ops/scripts/site_cert_report.py --days 30
```

Directive helper:

```bash
python3 /path/to/site-tools/skills/sitectl-ops/scripts/site_automation_templates.py --format directives --template weekly-cert-report
```

## Safety guidance

- Prefer audit/reporting jobs over automatic mutation.
- If the user wants automated remediation, default to preview mode first:
  - `python3 /path/to/site-tools/skills/sitectl-ops/scripts/site_fleet_autofix.py --only-problems --max-priority medium`
- `site_fleet_autofix.py` policy now supports:
  - command allowlist and denylist
  - domain allowlist and denylist
  - per-command `max_priority`
  - per-command `require_dry_run`
- Only use `--apply` when the user explicitly asks for automated fixes and understands the scope.
