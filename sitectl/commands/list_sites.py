from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    listings = site_service.list_sites()
    if not listings:
        print("No sites found.")
        return 0

    for item in listings:
        print(f"{item.domain}\t{item.type}")
    return 0

