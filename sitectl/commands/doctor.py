from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    report = site_service.run_doctor()
    all_ok = True
    for check in report.checks:
        status = "OK" if check.ok else "FAIL"
        if not check.ok:
            all_ok = False
        print(f"[{status}] {check.name}: {check.detail}")
    return 0 if all_ok else 1
