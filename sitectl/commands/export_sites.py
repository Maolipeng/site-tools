from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    result = site_service.export_sites(args.output)
    if args.output:
        print(f"Exported sites to {result}")
    else:
        print(result)
    return 0
