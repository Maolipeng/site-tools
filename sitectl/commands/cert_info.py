from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    info = site_service.get_certificate_info(args.domain)
    print(f"domain: {info.domain}")
    print(f"ssl_mode: {info.ssl_mode}")
    print(f"cert_path: {info.cert_path}")
    print(f"key_path: {info.key_path}")
    print(f"exists: {info.exists}")
    print(f"subject: {info.subject}")
    print(f"issuer: {info.issuer}")
    print(f"not_before: {info.not_before}")
    print(f"not_after: {info.not_after}")
    print(f"days_remaining: {info.days_remaining}")
    return 0
