from __future__ import annotations

import argparse

from sitectl.models import OperationPreview
from sitectl.services.site_service import SiteService


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{text}{suffix}: ").strip()
    if value:
        return value
    return default or ""


def _prompt_yes_no(text: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        value = input(f"{text} [{hint}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer y or n.")


def _prompt_int(text: str, default: int | None = None) -> int | None:
    raw = _prompt(text, str(default) if default is not None else None)
    if not raw:
        return default
    return int(raw)


def _print_preview(preview: OperationPreview) -> None:
    print(f"DRY RUN: {preview.title}")
    for action in preview.actions:
        print(f"- {action}")
    if preview.config_path and preview.config_content:
        print(f"\nConfig path: {preview.config_path}")
        print(preview.config_content)


def _create_site(site_service: SiteService) -> None:
    print("\nCreate Site")
    domain = _prompt("Domain")
    site_type = _prompt("Type (node/proxy/static/systemd)", "proxy")
    root = None
    port = None
    pm2_name = None
    service_name = None
    upstream_host = None

    if site_type in {"node", "static"}:
        root = _prompt("Project/root path")
    if site_type in {"node", "proxy", "systemd"}:
        port = _prompt_int("Port", 8080)
        upstream_host = _prompt("Upstream host", "127.0.0.1")
    if site_type == "node":
        pm2_name = _prompt("PM2 process name", domain.replace(".", "-"))
    if site_type == "systemd":
        service_name = _prompt("systemd service name")

    ssl_mode = _prompt("SSL mode (letsencrypt/manual)", "letsencrypt")
    email = _prompt("Email for Let's Encrypt", "") if ssl_mode == "letsencrypt" else None
    ssl_cert = _prompt("Certificate path", "") if ssl_mode == "manual" else None
    ssl_key = _prompt("Private key path", "") if ssl_mode == "manual" else None
    aliases_raw = _prompt("Aliases (comma-separated)", "")
    aliases = [item.strip() for item in aliases_raw.split(",") if item.strip()] or None
    listen_ipv6 = _prompt_yes_no("Enable IPv6 listen directives?", False)
    force = _prompt_yes_no("Overwrite existing config if present?", False)
    dry_run = _prompt_yes_no("Preview only?", False)

    result = site_service.create_site(
        domain=domain,
        site_type=site_type,
        root=root,
        port=port,
        pm2_name=pm2_name,
        service_name=service_name,
        email=email or None,
        aliases=aliases,
        listen_ipv6=listen_ipv6,
        upstream_host=upstream_host or None,
        ssl_mode=ssl_mode,
        ssl_cert_path=ssl_cert or None,
        ssl_key_path=ssl_key or None,
        force=force,
        dry_run=dry_run,
    )
    if isinstance(result, OperationPreview):
        _print_preview(result)
        return
    print(f"Created site {result.domain} ({result.type.value})")


def _list_sites(site_service: SiteService) -> None:
    listings = site_service.list_sites()
    if not listings:
        print("No sites found.")
        return
    for item in listings:
        print(f"{item.domain}\t{item.type}")


def _status(site_service: SiteService) -> None:
    domain = _prompt("Domain")
    status = site_service.get_status(domain)
    print(f"domain: {status.domain}")
    print(f"type: {status.type}")
    print(f"ssl_mode: {status.ssl_mode}")
    print(f"listen_ipv6: {status.listen_ipv6}")
    print(f"upstream_host: {status.upstream_host}")
    print(f"nginx_config_exists: {status.config_exists}")
    print(f"enabled_symlink_exists: {status.enabled_exists}")
    print(f"certificate_exists: {status.cert_exists}")
    print(f"pm2_process_exists: {status.pm2_exists}")
    print(f"systemd_service_active: {status.systemd_active}")
    print(f"port_open: {status.port_open}")


def _doctor(site_service: SiteService) -> None:
    domain = _prompt("Domain (optional)", "") or None
    report = site_service.run_doctor(domain=domain)
    for check in report.checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.detail}")


def _remove(site_service: SiteService) -> None:
    domain = _prompt("Domain")
    dry_run = _prompt_yes_no("Preview only?", False)
    result = site_service.remove_site(domain, dry_run=dry_run)
    if isinstance(result, OperationPreview):
        _print_preview(result)
        return
    print(f"Removed site {result}")


def _logs(site_service: SiteService) -> None:
    domain = _prompt("Domain")
    kind = _prompt("Log type (error/access/pm2/systemd)", "error")
    lines = _prompt_int("Lines", 100) or 100
    result = site_service.get_logs(domain, kind, lines=lines)
    print(f"Source: {result.source}")
    if result.content:
      print(result.content)


def _renew(site_service: SiteService) -> None:
    domain = _prompt("Domain (optional)", "") or None
    dry_run = _prompt_yes_no("Preview only?", False)
    result = site_service.renew_certificates(domain, dry_run=dry_run)
    if isinstance(result, OperationPreview):
        _print_preview(result)
        return
    print(f"Renewed certificates for {result}.")


def _reload(site_service: SiteService) -> None:
    dry_run = _prompt_yes_no("Preview only?", False)
    result = site_service.reload_nginx(dry_run=dry_run)
    if isinstance(result, OperationPreview):
        _print_preview(result)
        return
    print("Nginx reloaded successfully.")


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    actions = {
        "1": ("List sites", _list_sites),
        "2": ("Show site status", _status),
        "3": ("Run doctor", _doctor),
        "4": ("Create site", _create_site),
        "5": ("Remove site", _remove),
        "6": ("Show logs", _logs),
        "7": ("Renew certificates", _renew),
        "8": ("Reload Nginx", _reload),
        "0": ("Exit", None),
    }

    try:
        while True:
            print("\nsitectl interactive")
            for key, (label, _) in actions.items():
                print(f"{key}. {label}")
            choice = input("Select an action: ").strip()
            if choice == "0":
                print("Exiting.")
                return 0
            action = actions.get(choice)
            if action is None:
                print("Invalid selection.")
                continue
            _, handler = action
            if handler is not None:
                print()
                handler(site_service)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except EOFError:
        print("\nExiting.")
        return 0
