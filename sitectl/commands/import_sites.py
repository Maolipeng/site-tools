from __future__ import annotations

import argparse

from sitectl.models import OperationPreview
from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    result = site_service.import_sites(args.input, force=args.force, dry_run=args.dry_run)
    if isinstance(result, OperationPreview):
        print(f"DRY RUN: {result.title}")
        for action in result.actions:
            print(f"- {action}")
        return 0
    print(result)
    return 0
