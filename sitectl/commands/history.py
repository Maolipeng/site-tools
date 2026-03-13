from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    backups = site_service.list_history(args.domain)
    if not backups:
        print("No backups found.")
        return 0
    for backup in backups:
        print(f"{backup.name}\tmetadata={backup.has_metadata}")
    return 0
