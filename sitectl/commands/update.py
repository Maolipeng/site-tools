from __future__ import annotations

import argparse

from sitectl.models import OperationPreview
from sitectl.services.site_service import SiteService


def _print_preview(preview: OperationPreview) -> None:
    print(f"DRY RUN: {preview.title}")
    for action in preview.actions:
        print(f"- {action}")
    if preview.config_path and preview.config_content:
        print(f"\nConfig path: {preview.config_path}")
        print(preview.config_content)


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    result = site_service.update_site(
        domain=args.domain,
        site_type=args.type,
        root=args.root,
        port=args.port,
        pm2_name=args.pm2_name,
        service_name=args.service_name,
        email=args.email,
        aliases=args.alias,
        clear_aliases=args.clear_aliases,
        listen_ipv6=args.listen_ipv6,
        upstream_host=args.upstream_host,
        ssl_mode=args.ssl_mode,
        ssl_cert_path=args.ssl_cert,
        ssl_key_path=args.ssl_key,
        dry_run=args.dry_run,
    )
    if isinstance(result, OperationPreview):
        _print_preview(result)
        return 0
    print(f"Updated site {result.domain} ({result.type.value})")
    return 0
