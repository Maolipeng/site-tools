---
name: "sitectl-ops"
description: "Use when the user wants to manage Linux site deployments with sitectl, including creating or updating node/proxy/static/systemd sites, checking status and logs, running health checks, managing Let's Encrypt or manual certificates, handling IPv6 and AAAA readiness, reloading nginx, exporting/importing configs, and rolling back changes."
---

# SiteCtl Ops Skill

## When to use

- Create, update, remove, list, reload, or inspect `sitectl` sites.
- Manage Node/PM2, reverse-proxy, static, or existing systemd-backed sites.
- Check deployment health, Nginx status, logs, or environment readiness.
- Prepare IPv6-enabled home-server or NAS deployments, including AAAA readiness and HTTPS suggestions.
- Inspect, verify, warn on, renew, or replace certificates.
- Export/import site bundles or roll back to a previous backup.

## Preconditions

- Prefer running from the `sitectl` project root when the package is not installed globally.
- If `sitectl` is not on `PATH`, use `python -m sitectl ...` or the venv launcher path.
- For mutating commands that support `--dry-run`, use it first when the change is risky, broad, or ambiguous.
- When the user mentions a home machine, NAS, or public IPv6 instead of a traditional server, prefer `doctor --domain ... --listen-ipv6 ...` before issuing create/update guidance.
- `sitectl` auto-detects common Nginx layouts from `nginx.conf`, including `/etc/nginx`, `/opt/homebrew/etc/nginx`, and `/usr/local/etc/nginx`. Only reach for `SITECTL_NGINX_*` overrides when the install layout is custom or the user has already pinned those env vars.

## Prefer bundled scripts

Use the bundled scripts before hand-writing command sequences:

- Structured JSON output:
  - `scripts/site_json.py list`
  - `scripts/site_json.py status DOMAIN`
  - `scripts/site_json.py cert-info DOMAIN`
  - `scripts/site_json.py cert-expiring --days N`
  - `scripts/site_json.py cert-warn --days N`
  - `scripts/site_json.py history DOMAIN`
  - `scripts/site_json.py export [--output FILE]`
  - `scripts/site_json.py healthcheck DOMAIN`
  - `scripts/site_json.py cert-verify DOMAIN`
  - `scripts/site_json.py logs DOMAIN --kind error --lines 200`
  - `scripts/site_json.py doctor`
  - `scripts/site_json.py doctor --domain home.example.com --type proxy --port 8080 --upstream-host ::1 --listen-ipv6 --email ops@example.com`
  - `scripts/site_json.py preview-create ...`
  - `scripts/site_json.py preview-update DOMAIN ...`
  - `scripts/site_json.py preview-remove DOMAIN`
  - `scripts/site_json.py preview-reload`
  - `scripts/site_json.py preview-renew [DOMAIN]`
  - `scripts/site_json.py preview-cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH`
  - `scripts/site_json.py preview-import --input FILE [--force]`
  - `scripts/site_json.py preview-rollback DOMAIN --backup BACKUP`
  - `scripts/site_json.py apply-create ...`
  - `scripts/site_json.py apply-update DOMAIN ...`
  - `scripts/site_json.py apply-remove DOMAIN`
  - `scripts/site_json.py apply-reload`
  - `scripts/site_json.py apply-renew [DOMAIN]`
  - `scripts/site_json.py apply-cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH`
  - `scripts/site_json.py apply-import --input FILE [--force]`
  - `scripts/site_json.py apply-rollback DOMAIN --backup BACKUP`
  - `scripts/site_json.py apply-export [--output FILE]`
  - `scripts/site_json.py apply-history DOMAIN`
  - Add `--trace-id TRACE_ID --request-id REQUEST_ID` when a caller needs stable correlation ids
- Full audit report:
  - `scripts/site_audit.py DOMAIN`
  - Add `--include-runtime-log` to include PM2 or systemd logs
- Batch certificate report:
  - `scripts/site_cert_report.py --days 30`
- Batch site audit:
  - `scripts/site_fleet_audit.py`
  - Returns global recommendations and global autofix candidates
- Batch autofix executor:
  - `scripts/site_fleet_autofix.py`
  - Defaults to preview mode; add `--apply` to execute supported candidates
  - Reads command, domain, and priority policy controls from `assets/autofix-policy.json`
- Automation templates:
  - `scripts/site_automation_templates.py --format json`
  - `scripts/site_automation_templates.py --format directives`
  - Use when the user wants recurring sitectl automations
- Status summary:
  - `scripts/site_status.sh DOMAIN`
- Health check:
  - `scripts/site_healthcheck.sh DOMAIN [healthcheck options...]`
- Certificate/key match:
  - `scripts/site_cert_verify.sh DOMAIN`
- Safe create wrapper:
  - `scripts/site_safe_create.sh [create options...]`
  - Add `--apply` to execute after the dry run preview
- Safe update wrapper:
  - `scripts/site_safe_update.sh DOMAIN [update options...]`
  - Add `--apply` to execute after the dry run preview
- Safe remove wrapper:
  - `scripts/site_safe_remove.sh DOMAIN`
  - Add `--apply` to execute after the dry run preview

These scripts auto-resolve `sitectl` from `PATH`, the repo venv, or `python3 -m sitectl`.

## Default workflow

1. Identify the target site and current state.
   - Use `scripts/site_json.py list`, `scripts/site_status.sh DOMAIN`, `scripts/site_json.py cert-info DOMAIN`, or `scripts/site_json.py doctor` as needed.
   - For IPv6-facing or home-network deployments, prefer `scripts/site_json.py doctor --domain ... --type ... --port ... --upstream-host ... --listen-ipv6` first.
   - If the user is on macOS/Homebrew or reports `/etc/nginx` mismatches, assume `sitectl` should detect the active Nginx layout first; verify with `scripts/site_json.py doctor` before suggesting manual path overrides.
2. Choose the narrowest `sitectl` command that matches the request.
3. For create/update/remove/import/rollback/reload/renew/cert-replace, prefer a dry run before the live command when it adds safety.
   - If the plan includes `--listen-ipv6` and `letsencrypt`, check AAAA readiness before treating certificate issuance as safe.
4. After a live change, verify the result.
   - Use `scripts/site_status.sh DOMAIN`
   - Use `scripts/site_healthcheck.sh DOMAIN`
   - Use `sitectl logs DOMAIN --error`
   - Use `sitectl cert-info DOMAIN` or `scripts/site_cert_verify.sh DOMAIN` when certificate-related

## References

Read only the reference file that matches the task:

- Certificates:
  - `references/certs.md`
- Backups, rollback, export, import:
  - `references/recovery.md`
- Site-type specific flags and behavior:
  - `references/site-types.md`
- Post-change debugging and diagnosis:
  - `references/troubleshooting.md`
- Recurring checks and automation ideas:
  - `references/automation.md`

## Quick command map

- Create:
  - `sitectl create --domain DOMAIN --type TYPE ...`
- Update:
  - `sitectl update DOMAIN ...`
- Remove:
  - `sitectl remove DOMAIN`
- List:
  - `sitectl list`
- Status:
  - `sitectl status DOMAIN`
- Reload:
  - `sitectl reload`
- Logs:
  - `sitectl logs DOMAIN --error|--access|--pm2|--systemd`
- Health:
  - `sitectl healthcheck DOMAIN`
- Renew:
  - `sitectl renew [DOMAIN]`
- Certificate inspection:
  - `sitectl cert-info DOMAIN`
  - `sitectl cert-expiring --days N`
  - `sitectl cert-warn --days N`
  - `sitectl cert-verify DOMAIN`
  - `sitectl cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH`
- Recovery:
  - `sitectl history DOMAIN`
  - `sitectl rollback DOMAIN --backup BACKUP`
  - `sitectl export --output FILE`
  - `sitectl import --input FILE [--force]`
- Environment diagnostics:
  - `sitectl doctor`

## Important constraints

- `renew` only applies to `letsencrypt` sites.
- `cert-replace` only applies to `manual` certificate sites.
- `remove` does not delete the app directory, static files, or certificate files.
- `systemd` support manages an existing service; it does not generate unit files.
- `node` sites require a valid `package.json` in `--root`.
- `node` sites pick `pnpm`, `yarn`, or `npm` from `packageManager` or lockfiles before install/build/start commands.
- `static` sites require an existing directory in `--root`.
- Use `--listen-ipv6` when the site should emit explicit `listen [::]` directives.
- Use `--upstream-host ::1` or another host when the app is not bound to `127.0.0.1`.
- `doctor --domain ...` can check whether AAAA already points at the host and suggest the next `sitectl create` shape.
- `SITECTL_NGINX_MAIN_CONFIG` changes the derived default `sites-available`, `sites-enabled`, and `snippets` directories unless those are explicitly overridden too.

## High-signal examples

```bash
bash scripts/site_safe_create.sh --domain app.example.com --type node --root /srv/app --port 3000 --pm2-name app-example --email ops@example.com
bash scripts/site_safe_create.sh --domain app.example.com --type node --root /srv/app --port 3000 --pm2-name app-example --email ops@example.com --apply
bash scripts/site_safe_create.sh --domain ipv6.example.com --type proxy --port 8080 --upstream-host ::1 --listen-ipv6 --email ops@example.com --apply
```

```bash
bash scripts/site_safe_update.sh api.example.com --port 9090 --alias www.example.com
bash scripts/site_safe_update.sh api.example.com --port 9090 --alias www.example.com --apply
```

```bash
python3 scripts/site_json.py status app.example.com
python3 scripts/site_json.py cert-verify secure.example.com
python3 scripts/site_json.py cert-warn --days 14
python3 scripts/site_json.py preview-update app.example.com --port 9090
python3 scripts/site_json.py apply-reload
python3 scripts/site_json.py preview-rollback app.example.com --backup 20260313153000123456
python3 scripts/site_json.py apply-export --output /tmp/sitectl-bundle.json
```

```bash
bash scripts/site_safe_remove.sh app.example.com
bash scripts/site_safe_remove.sh app.example.com --apply
```

```bash
python3 scripts/site_audit.py app.example.com --path /healthz --include-runtime-log
python3 scripts/site_cert_report.py --days 14
python3 scripts/site_fleet_audit.py --include-runtime-log
python3 scripts/site_fleet_autofix.py --only-problems --max-priority medium
```
