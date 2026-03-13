from __future__ import annotations

import argparse

from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    report = site_service.run_doctor(
        domain=args.domain,
        site_type=args.type,
        port=args.port,
        upstream_host=args.upstream_host,
        listen_ipv6=args.listen_ipv6,
        email=args.email,
        ssl_mode=args.ssl_mode,
    )
    all_ok = True
    for check in report.checks:
        status = "OK" if check.ok else "FAIL"
        if not check.ok:
            all_ok = False
        print(f"[{status}] {check.name}: {check.detail}")
    if report.advice:
        print("\nAdvice:")
        for item in report.advice:
            print(f"- [{item.level.upper()}] {item.title}: {item.detail}")
            for command in item.commands:
                print(f"  {command}")
    return 0 if all_ok else 1
