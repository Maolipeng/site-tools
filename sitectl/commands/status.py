from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    status = site_service.get_status(args.domain)
    print(f"domain: {status.domain}")
    print(f"type: {status.type}")
    print(f"ssl_mode: {status.ssl_mode}")
    print(f"nginx_config_exists: {status.config_exists}")
    print(f"enabled_symlink_exists: {status.enabled_exists}")
    print(f"certificate_exists: {status.cert_exists}")
    print(f"pm2_process_exists: {status.pm2_exists}")
    print(f"systemd_service_active: {status.systemd_active}")
    print(f"port_open: {status.port_open}")
    return 0
