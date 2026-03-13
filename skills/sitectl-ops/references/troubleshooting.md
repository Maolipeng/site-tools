# Troubleshooting

Use this reference when the task is about diagnosis after a failed deploy or an unhealthy site.

## Fast triage

1. `sitectl status DOMAIN`
2. `sitectl healthcheck DOMAIN`
3. `sitectl logs DOMAIN --error --lines 200`

Then branch by runtime:

- Node:
  - `sitectl logs DOMAIN --pm2 --lines 200`
- systemd:
  - `sitectl logs DOMAIN --systemd --lines 200`

## Global environment checks

- `sitectl doctor`
- `sitectl doctor --domain DOMAIN --type proxy --port PORT --upstream-host ::1 --listen-ipv6`
- `sitectl reload --dry-run`

## Certificate-specific checks

- `sitectl cert-info DOMAIN`
- `sitectl cert-verify DOMAIN`
- `sitectl cert-expiring --days 14`

## Common recovery sequence

1. `sitectl history DOMAIN`
2. `sitectl rollback DOMAIN --backup BACKUP --dry-run`
3. `sitectl rollback DOMAIN --backup BACKUP`
4. `sitectl healthcheck DOMAIN`

## IPv6-specific triage

Use this branch when the user is exposing a home machine, NAS, or other public IPv6 endpoint:

1. `sitectl doctor --domain DOMAIN --type proxy --port PORT --upstream-host ::1 --listen-ipv6 --email ...`
2. Confirm `network:global-ipv6` is healthy
3. Confirm `dns:aaaa:DOMAIN` points at the same host
4. Only then treat `letsencrypt` issuance or remote HTTPS failures as an application/Nginx problem
