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
    result = site_service.replace_manual_certificate(
        args.domain,
        ssl_cert_path=args.ssl_cert,
        ssl_key_path=args.ssl_key,
        dry_run=args.dry_run,
    )
    if isinstance(result, OperationPreview):
        _print_preview(result)
        return 0
    print(f"Replaced manual certificate for {result.domain}.")
    return 0
