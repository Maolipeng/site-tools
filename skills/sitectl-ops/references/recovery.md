# Recovery

Use this reference when the task is about cautious changes, backups, exports/imports, or rollback.

## Safe change order

1. Inspect current state:
   - `sitectl status DOMAIN`
   - `sitectl history DOMAIN`
2. Preview the change:
   - `sitectl update DOMAIN ... --dry-run`
   - `sitectl import --input FILE --dry-run`
   - `sitectl rollback DOMAIN --backup BACKUP --dry-run`
3. Apply the change.
4. Verify:
   - `sitectl status DOMAIN`
   - `sitectl healthcheck DOMAIN`
   - `sitectl logs DOMAIN --error`

## Backups and rollback

- List backups:
  - `sitectl history DOMAIN`
- Roll back:
  - `sitectl rollback DOMAIN --backup BACKUP`

Rollback restores:

- Nginx config
- State metadata when available
- PM2 runtime for Node sites when metadata supports it
- systemd runtime for systemd sites when metadata supports it

## Export and import

- Export:
  - `sitectl export --output /tmp/sitectl-bundle.json`
- Import:
  - `sitectl import --input /tmp/sitectl-bundle.json [--force]`

Import restores configuration and state, but does not recreate PM2 or restart systemd services.
