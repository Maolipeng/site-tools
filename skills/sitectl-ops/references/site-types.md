# Site Types

Use this reference when choosing command flags for a specific site type.

## `node`

Required:

- `--root`
- `--port`
- `--pm2-name`
- `--email` for `letsencrypt`

Behavior:

- Validates `package.json`
- Runs `npm install`
- Runs `npm run build` when a build script exists
- Starts or restarts `npm run start` with PM2

## `proxy`

Required:

- `--port`
- `--email` for `letsencrypt`

Behavior:

- Does not start the application
- Generates only the Nginx reverse-proxy config
- Can target IPv6-local upstreams such as `--upstream-host ::1`

## `static`

Required:

- `--root`
- `--email` for `letsencrypt`

Behavior:

- Validates the directory exists
- Uses SPA-friendly `try_files $uri $uri/ /index.html`
- Can still enable public IPv6 listeners with `--listen-ipv6`

## `systemd`

Required:

- `--port`
- `--service-name`
- `--email` for `letsencrypt`

Behavior:

- Assumes the systemd service already exists
- Restarts the service during create/update
- Can read logs via `journalctl`

## IPv6 notes

- Use `--listen-ipv6` to emit explicit `listen [::]:80;` and `listen [::]:443 ssl;`.
- Use `--upstream-host ::1` when the local app only binds IPv6 loopback.
- For public IPv6 plus Let's Encrypt, run `sitectl doctor --domain DOMAIN --type TYPE --port PORT --upstream-host ::1 --listen-ipv6 --email ...` before assuming certificate issuance is ready.
