from __future__ import annotations

import argparse

from sitectl.exceptions import ValidationError
from sitectl.services.site_service import SiteService


def run(args: argparse.Namespace, site_service: SiteService) -> int:
    if args.timeout <= 0:
        raise ValidationError("--timeout must be greater than 0.")
    if args.skip_local and args.skip_remote:
        raise ValidationError("Cannot skip both local and remote health checks.")

    report = site_service.run_healthcheck(
        args.domain,
        path=args.path,
        timeout=args.timeout,
        skip_local=args.skip_local,
        skip_remote=args.skip_remote,
        remote_url=args.remote_url,
    )
    print(f"domain: {report.domain}")
    print(f"type: {report.type}")
    all_ok = True
    for probe in report.probes:
        status = "OK" if probe.ok else "FAIL"
        if not probe.ok:
            all_ok = False
        suffix = f" (status={probe.status_code})" if probe.status_code is not None else ""
        print(f"[{status}] {probe.name}: {probe.detail}{suffix}")
    return 0 if all_ok else 1
