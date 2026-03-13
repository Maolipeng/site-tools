from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    result = site_service.verify_certificate(args.domain)
    print(f"domain: {result.domain}")
    print(f"ssl_mode: {result.ssl_mode}")
    print(f"cert_path: {result.cert_path}")
    print(f"key_path: {result.key_path}")
    print(f"cert_exists: {result.cert_exists}")
    print(f"key_exists: {result.key_exists}")
    print(f"matches: {result.matches}")
    print(f"detail: {result.detail}")
    return 0 if result.matches else 1
