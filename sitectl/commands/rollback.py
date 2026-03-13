from __future__ import annotations

import argparse

from sitectl.models import OperationPreview
from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    result = site_service.rollback_site(args.domain, args.backup, dry_run=args.dry_run)
    if isinstance(result, OperationPreview):
        print(f"DRY RUN: {result.title}")
        for action in result.actions:
            print(f"- {action}")
        return 0
    print(result)
    return 0
