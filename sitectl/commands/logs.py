from __future__ import annotations

import argparse

from sitectl.exceptions import ValidationError
from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    if args.lines < 1:
        raise ValidationError("--lines must be greater than 0.")
    kind = site_service.log_service.resolve_log_kind(args.access, args.error, args.pm2, args.systemd)
    result = site_service.get_logs(args.domain, kind, lines=args.lines)
    print(f"Source: {result.source}")
    if result.content:
        print(result.content)
    return 0
