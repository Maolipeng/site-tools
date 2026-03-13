from __future__ import annotations

import argparse

from sitectl.exceptions import ValidationError
from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    if args.days < 0:
        raise ValidationError("--days must be 0 or greater.")
    items = site_service.list_expiring_certificates(args.days)
    if not items:
        print("OK: no certificates expiring within threshold.")
        return 0
    for item in items:
        print(f"WARN\t{item.domain}\tmode={item.ssl_mode}\texists={item.exists}\tdays_remaining={item.days_remaining}\t{item.cert_path}")
    return 1
