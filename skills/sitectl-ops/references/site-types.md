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

## `static`

Required:

- `--root`
- `--email` for `letsencrypt`

Behavior:

- Validates the directory exists
- Uses SPA-friendly `try_files $uri $uri/ /index.html`

## `systemd`

Required:

- `--port`
- `--service-name`
- `--email` for `letsencrypt`

Behavior:

- Assumes the systemd service already exists
- Restarts the service during create/update
- Can read logs via `journalctl`
