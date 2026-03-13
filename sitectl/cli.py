from __future__ import annotations

import argparse
import sys

from sitectl.commands import create as create_command
from sitectl.commands import cert_expiring as cert_expiring_command
from sitectl.commands import cert_info as cert_info_command
from sitectl.commands import cert_replace as cert_replace_command
from sitectl.commands import cert_verify as cert_verify_command
from sitectl.commands import cert_warn as cert_warn_command
from sitectl.commands import doctor as doctor_command
from sitectl.commands import export_sites as export_command
from sitectl.commands import healthcheck as healthcheck_command
from sitectl.commands import history as history_command
from sitectl.commands import import_sites as import_command
from sitectl.commands import list_sites as list_command
from sitectl.commands import logs as logs_command
from sitectl.commands import reload as reload_command
from sitectl.commands import rollback as rollback_command
from sitectl.commands import remove as remove_command
from sitectl.commands import renew as renew_command
from sitectl.commands import status as status_command
from sitectl.commands import update as update_command
from sitectl.config import SiteCtlConfig
from sitectl.exceptions import SiteCtlError
from sitectl.logger import get_logger
from sitectl.services.certbot_service import CertbotService
from sitectl.services.certificate_service import CertificateService
from sitectl.services.doctor_service import DoctorService
from sitectl.services.healthcheck_service import HealthcheckService
from sitectl.services.log_service import LogService
from sitectl.services.nginx_service import NginxService
from sitectl.services.pm2_service import PM2Service
from sitectl.services.site_service import SiteService
from sitectl.services.status_service import StatusService
from sitectl.services.systemd_service import SystemdService
from sitectl.services.system_service import SystemService


LOGGER = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sitectl", description="Manage Nginx site deployments.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a new site.")
    create_parser.add_argument("--domain", required=True, help="Site domain.")
    create_parser.add_argument("--type", required=True, choices=["node", "proxy", "static", "systemd"], help="Site type.")
    create_parser.add_argument("--root", help="Project root or static site root.")
    create_parser.add_argument("--port", type=int, help="Local service port.")
    create_parser.add_argument("--pm2-name", help="PM2 process name for node sites.")
    create_parser.add_argument("--service-name", help="systemd service name for systemd sites.")
    create_parser.add_argument("--alias", action="append", default=[], help="Additional server_name alias, can be repeated.")
    create_parser.add_argument("--ssl-mode", choices=["letsencrypt", "manual"], default="letsencrypt", help="TLS certificate mode.")
    create_parser.add_argument("--ssl-cert", help="Path to an existing TLS certificate file for manual mode.")
    create_parser.add_argument("--ssl-key", help="Path to an existing TLS private key file for manual mode.")
    create_parser.add_argument("--email", help="Email for Let's Encrypt.")
    create_parser.add_argument("--force", action="store_true", help="Overwrite existing Nginx config.")
    create_parser.add_argument("--dry-run", action="store_true", help="Preview actions without making changes.")
    create_parser.set_defaults(handler=create_command.run)

    update_parser = subparsers.add_parser("update", help="Update an existing site.")
    update_parser.add_argument("domain", help="Site domain.")
    update_parser.add_argument("--type", choices=["node", "proxy", "static", "systemd"], help="New site type.")
    update_parser.add_argument("--root", help="Project root or static site root.")
    update_parser.add_argument("--port", type=int, help="Local service port.")
    update_parser.add_argument("--pm2-name", help="PM2 process name for node sites.")
    update_parser.add_argument("--service-name", help="systemd service name for systemd sites.")
    update_parser.add_argument("--alias", action="append", help="Replace aliases with the provided values.")
    update_parser.add_argument("--clear-aliases", action="store_true", help="Remove all configured aliases.")
    update_parser.add_argument("--ssl-mode", choices=["letsencrypt", "manual"], help="TLS certificate mode.")
    update_parser.add_argument("--ssl-cert", help="Path to an existing TLS certificate file for manual mode.")
    update_parser.add_argument("--ssl-key", help="Path to an existing TLS private key file for manual mode.")
    update_parser.add_argument("--email", help="Email for Let's Encrypt.")
    update_parser.add_argument("--dry-run", action="store_true", help="Preview actions without making changes.")
    update_parser.set_defaults(handler=update_command.run)

    remove_parser = subparsers.add_parser("remove", help="Remove a site.")
    remove_parser.add_argument("domain", help="Site domain.")
    remove_parser.add_argument("--dry-run", action="store_true", help="Preview actions without making changes.")
    remove_parser.set_defaults(handler=remove_command.run)

    list_parser = subparsers.add_parser("list", help="List managed sites.")
    list_parser.set_defaults(handler=list_command.run)

    cert_info_parser = subparsers.add_parser("cert-info", help="Inspect certificate details for a site.")
    cert_info_parser.add_argument("domain", help="Site domain.")
    cert_info_parser.set_defaults(handler=cert_info_command.run)

    cert_expiring_parser = subparsers.add_parser("cert-expiring", help="List certificates that are missing or expiring soon.")
    cert_expiring_parser.add_argument("--days", type=int, default=30, help="Days threshold for expiration warnings.")
    cert_expiring_parser.set_defaults(handler=cert_expiring_command.run)

    cert_warn_parser = subparsers.add_parser("cert-warn", help="Emit certificate expiry warnings and return non-zero when issues exist.")
    cert_warn_parser.add_argument("--days", type=int, default=30, help="Days threshold for expiration warnings.")
    cert_warn_parser.set_defaults(handler=cert_warn_command.run)

    cert_verify_parser = subparsers.add_parser("cert-verify", help="Verify that a certificate and private key match.")
    cert_verify_parser.add_argument("domain", help="Site domain.")
    cert_verify_parser.set_defaults(handler=cert_verify_command.run)

    cert_replace_parser = subparsers.add_parser("cert-replace", help="Replace the certificate files for a manual TLS site.")
    cert_replace_parser.add_argument("domain", help="Site domain.")
    cert_replace_parser.add_argument("--ssl-cert", required=True, help="Path to a replacement TLS certificate file.")
    cert_replace_parser.add_argument("--ssl-key", required=True, help="Path to a replacement TLS private key file.")
    cert_replace_parser.add_argument("--dry-run", action="store_true", help="Preview actions without making changes.")
    cert_replace_parser.set_defaults(handler=cert_replace_command.run)

    history_parser = subparsers.add_parser("history", help="List rollback backups for a site.")
    history_parser.add_argument("domain", help="Site domain.")
    history_parser.set_defaults(handler=history_command.run)

    export_parser = subparsers.add_parser("export", help="Export managed site state and configs.")
    export_parser.add_argument("--output", help="Write bundle to a JSON file instead of stdout.")
    export_parser.set_defaults(handler=export_command.run)

    import_parser = subparsers.add_parser("import", help="Import managed site state and configs from a bundle.")
    import_parser.add_argument("--input", required=True, help="Path to an export JSON bundle.")
    import_parser.add_argument("--force", action="store_true", help="Overwrite existing site configs during import.")
    import_parser.add_argument("--dry-run", action="store_true", help="Preview import actions without making changes.")
    import_parser.set_defaults(handler=import_command.run)

    rollback_parser = subparsers.add_parser("rollback", help="Rollback a site to a previous backup.")
    rollback_parser.add_argument("domain", help="Site domain.")
    rollback_parser.add_argument("--backup", required=True, help="Backup filename or timestamp suffix.")
    rollback_parser.add_argument("--dry-run", action="store_true", help="Preview rollback actions without making changes.")
    rollback_parser.set_defaults(handler=rollback_command.run)

    logs_parser = subparsers.add_parser("logs", help="Show recent logs for a site.")
    logs_parser.add_argument("domain", help="Site domain.")
    logs_parser.add_argument("--access", action="store_true", help="Show Nginx access log.")
    logs_parser.add_argument("--error", action="store_true", help="Show Nginx error log.")
    logs_parser.add_argument("--pm2", action="store_true", help="Show PM2 logs for node sites.")
    logs_parser.add_argument("--systemd", action="store_true", help="Show journalctl logs for systemd sites.")
    logs_parser.add_argument("--lines", type=int, default=100, help="Number of lines to show.")
    logs_parser.set_defaults(handler=logs_command.run)

    status_parser = subparsers.add_parser("status", help="Show site status.")
    status_parser.add_argument("domain", help="Site domain.")
    status_parser.set_defaults(handler=status_command.run)

    healthcheck_parser = subparsers.add_parser("healthcheck", help="Run local and remote health checks.")
    healthcheck_parser.add_argument("domain", help="Site domain.")
    healthcheck_parser.add_argument("--path", default="/", help="HTTP path to probe.")
    healthcheck_parser.add_argument("--timeout", type=float, default=5.0, help="Probe timeout in seconds.")
    healthcheck_parser.add_argument("--skip-local", action="store_true", help="Skip local port and HTTP checks.")
    healthcheck_parser.add_argument("--skip-remote", action="store_true", help="Skip remote HTTPS check.")
    healthcheck_parser.add_argument("--remote-url", help="Override remote URL, useful for testing.")
    healthcheck_parser.set_defaults(handler=healthcheck_command.run)

    reload_parser = subparsers.add_parser("reload", help="Validate and reload Nginx.")
    reload_parser.add_argument("--dry-run", action="store_true", help="Preview actions without making changes.")
    reload_parser.set_defaults(handler=reload_command.run)

    renew_parser = subparsers.add_parser("renew", help="Renew certificates.")
    renew_parser.add_argument("domain", nargs="?", help="Optional certificate name/domain.")
    renew_parser.add_argument("--dry-run", action="store_true", help="Preview actions without making changes.")
    renew_parser.set_defaults(handler=renew_command.run)

    doctor_parser = subparsers.add_parser("doctor", help="Run environment health checks.")
    doctor_parser.set_defaults(handler=doctor_command.run)
    return parser


def build_site_service(config: SiteCtlConfig | None = None) -> SiteService:
    active_config = config or SiteCtlConfig.from_env()
    system_service = SystemService()
    systemd_service = SystemdService(system_service)
    nginx_service = NginxService(active_config, system_service)
    certbot_service = CertbotService(system_service)
    certificate_service = CertificateService(active_config, system_service)
    pm2_service = PM2Service(system_service)
    status_service = StatusService(active_config, nginx_service, pm2_service, systemd_service)
    log_service = LogService(system_service, systemd_service)
    doctor_service = DoctorService(active_config, system_service)
    healthcheck_service = HealthcheckService()
    return SiteService(
        active_config,
        nginx_service,
        certbot_service,
        pm2_service,
        status_service,
        log_service,
        doctor_service,
        systemd_service,
        healthcheck_service,
        certificate_service,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    site_service = build_site_service()

    try:
        return args.handler(args, site_service)
    except SiteCtlError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        LOGGER.debug("Command failed", exc_info=exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
