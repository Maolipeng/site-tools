# Certificates

Use this reference when the task is about TLS mode selection, certificate inspection, expiry review, renewal, or replacing manual certificates.

## Mode selection

- Use `letsencrypt` when automatic Certbot issuance and renewal are desired.
- Use `manual` when the user already has a certificate and key, for example Cloudflare Origin CA.

## Core commands

- Inspect certificate details:
  - `sitectl cert-info DOMAIN`
- Find expiring or missing certificates:
  - `sitectl cert-expiring --days N`
- Return non-zero for alerting:
  - `sitectl cert-warn --days N`
- Verify certificate/private key match:
  - `sitectl cert-verify DOMAIN`
- Replace manual certificate and reload Nginx:
  - `sitectl cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH`
- Renew Let's Encrypt:
  - `sitectl renew [DOMAIN]`

## Recommended workflows

### Inspect a certificate

1. `sitectl cert-info DOMAIN`
2. If the site uses manual certificates, optionally run `sitectl cert-verify DOMAIN`

### Rotate a manual certificate

1. `sitectl cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH --dry-run`
2. `sitectl cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH`
3. `sitectl cert-verify DOMAIN`
4. `sitectl healthcheck DOMAIN`

### Monitor expiry

1. `sitectl cert-warn --days 14`
2. Treat exit code `1` as an alert condition

## Constraints

- `renew` does not apply to `manual` sites.
- `cert-replace` only applies to `manual` sites.
- `cert-verify` requires `openssl`.
