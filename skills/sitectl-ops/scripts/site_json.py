#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
REPO_ROOT = SCRIPT_PATH.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sitectl.cli import build_site_service  # noqa: E402
from sitectl.exceptions import SiteCtlError  # noqa: E402
from json_envelope import build_meta  # noqa: E402


def _to_jsonable(value: object) -> object:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _command_mode(command_name: str) -> str:
    if command_name.startswith("preview-"):
        return "preview"
    if command_name.startswith("apply-"):
        return "apply"
    return "read"


def _emit_response(
    command_name: str,
    payload: object,
    *,
    ok: bool,
    exit_code: int,
    trace_id: str | None = None,
    request_id: str | None = None,
) -> int:
    response = {
        "ok": ok,
        "meta": build_meta(
            command_name,
            _command_mode(command_name),
            exit_code,
            trace_id=trace_id,
            request_id=request_id,
        ),
        "result": _to_jsonable(payload),
    }
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Structured JSON helpers for the sitectl-ops skill.")
    parser.add_argument("--trace-id", help="Optional trace identifier to propagate into JSON output.")
    parser.add_argument("--request-id", help="Optional request identifier to propagate into JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Return sitectl list output as JSON.")
    list_parser.set_defaults(command_name="list")

    status_parser = subparsers.add_parser("status", help="Return site status as JSON.")
    status_parser.add_argument("domain")
    status_parser.set_defaults(command_name="status")

    cert_info_parser = subparsers.add_parser("cert-info", help="Return certificate details as JSON.")
    cert_info_parser.add_argument("domain")
    cert_info_parser.set_defaults(command_name="cert-info")

    cert_expiring_parser = subparsers.add_parser("cert-expiring", help="Return expiring certificates as JSON.")
    cert_expiring_parser.add_argument("--days", type=int, default=30)
    cert_expiring_parser.set_defaults(command_name="cert-expiring")

    cert_warn_parser = subparsers.add_parser("cert-warn", help="Return certificate warnings as JSON.")
    cert_warn_parser.add_argument("--days", type=int, default=30)
    cert_warn_parser.set_defaults(command_name="cert-warn")

    history_parser = subparsers.add_parser("history", help="Return backup history as JSON.")
    history_parser.add_argument("domain")
    history_parser.set_defaults(command_name="history")

    export_parser = subparsers.add_parser("export", help="Return export output as JSON.")
    export_parser.add_argument("--output")
    export_parser.set_defaults(command_name="export")

    health_parser = subparsers.add_parser("healthcheck", help="Return healthcheck report as JSON.")
    health_parser.add_argument("domain")
    health_parser.add_argument("--path", default="/")
    health_parser.add_argument("--timeout", type=float, default=5.0)
    health_parser.add_argument("--skip-local", action="store_true")
    health_parser.add_argument("--skip-remote", action="store_true")
    health_parser.add_argument("--remote-url")
    health_parser.set_defaults(command_name="healthcheck")

    cert_verify_parser = subparsers.add_parser("cert-verify", help="Return certificate verification result as JSON.")
    cert_verify_parser.add_argument("domain")
    cert_verify_parser.set_defaults(command_name="cert-verify")

    logs_parser = subparsers.add_parser("logs", help="Return site logs as JSON.")
    logs_parser.add_argument("domain")
    logs_parser.add_argument("--kind", choices=["access", "error", "pm2", "systemd"], default="error")
    logs_parser.add_argument("--lines", type=int, default=100)
    logs_parser.set_defaults(command_name="logs")

    doctor_parser = subparsers.add_parser("doctor", help="Return doctor report as JSON.")
    doctor_parser.add_argument("--domain")
    doctor_parser.add_argument("--type", choices=["node", "proxy", "static", "systemd"])
    doctor_parser.add_argument("--port", type=int)
    doctor_parser.add_argument("--upstream-host")
    doctor_parser.add_argument("--listen-ipv6", action="store_true")
    doctor_parser.add_argument("--email")
    doctor_parser.add_argument("--ssl-mode", choices=["letsencrypt", "manual"], default="letsencrypt")
    doctor_parser.set_defaults(command_name="doctor")

    preview_create_parser = subparsers.add_parser("preview-create", help="Return a create dry-run preview as JSON.")
    preview_create_parser.add_argument("--domain", required=True)
    preview_create_parser.add_argument("--type", required=True, choices=["node", "proxy", "static", "systemd"])
    preview_create_parser.add_argument("--root")
    preview_create_parser.add_argument("--port", type=int)
    preview_create_parser.add_argument("--pm2-name")
    preview_create_parser.add_argument("--service-name")
    preview_create_parser.add_argument("--listen-ipv6", action="store_true")
    preview_create_parser.add_argument("--upstream-host")
    preview_create_parser.add_argument("--alias", action="append", default=[])
    preview_create_parser.add_argument("--ssl-mode", choices=["letsencrypt", "manual"], default="letsencrypt")
    preview_create_parser.add_argument("--ssl-cert")
    preview_create_parser.add_argument("--ssl-key")
    preview_create_parser.add_argument("--email")
    preview_create_parser.add_argument("--force", action="store_true")
    preview_create_parser.set_defaults(command_name="preview-create")

    preview_update_parser = subparsers.add_parser("preview-update", help="Return an update dry-run preview as JSON.")
    preview_update_parser.add_argument("domain")
    preview_update_parser.add_argument("--type", choices=["node", "proxy", "static", "systemd"])
    preview_update_parser.add_argument("--root")
    preview_update_parser.add_argument("--port", type=int)
    preview_update_parser.add_argument("--pm2-name")
    preview_update_parser.add_argument("--service-name")
    preview_update_parser.add_argument("--listen-ipv6", dest="listen_ipv6", action="store_true")
    preview_update_parser.add_argument("--no-listen-ipv6", dest="listen_ipv6", action="store_false")
    preview_update_parser.add_argument("--upstream-host")
    preview_update_parser.add_argument("--alias", action="append")
    preview_update_parser.add_argument("--clear-aliases", action="store_true")
    preview_update_parser.set_defaults(listen_ipv6=None)
    preview_update_parser.add_argument("--ssl-mode", choices=["letsencrypt", "manual"])
    preview_update_parser.add_argument("--ssl-cert")
    preview_update_parser.add_argument("--ssl-key")
    preview_update_parser.add_argument("--email")
    preview_update_parser.set_defaults(command_name="preview-update")

    preview_remove_parser = subparsers.add_parser("preview-remove", help="Return a remove dry-run preview as JSON.")
    preview_remove_parser.add_argument("domain")
    preview_remove_parser.set_defaults(command_name="preview-remove")

    preview_reload_parser = subparsers.add_parser("preview-reload", help="Return a reload dry-run preview as JSON.")
    preview_reload_parser.set_defaults(command_name="preview-reload")

    preview_renew_parser = subparsers.add_parser("preview-renew", help="Return a renew dry-run preview as JSON.")
    preview_renew_parser.add_argument("domain", nargs="?")
    preview_renew_parser.set_defaults(command_name="preview-renew")

    preview_cert_replace_parser = subparsers.add_parser("preview-cert-replace", help="Return a cert-replace dry-run preview as JSON.")
    preview_cert_replace_parser.add_argument("domain")
    preview_cert_replace_parser.add_argument("--ssl-cert", required=True)
    preview_cert_replace_parser.add_argument("--ssl-key", required=True)
    preview_cert_replace_parser.set_defaults(command_name="preview-cert-replace")

    preview_import_parser = subparsers.add_parser("preview-import", help="Return an import dry-run preview as JSON.")
    preview_import_parser.add_argument("--input", required=True)
    preview_import_parser.add_argument("--force", action="store_true")
    preview_import_parser.set_defaults(command_name="preview-import")

    preview_rollback_parser = subparsers.add_parser("preview-rollback", help="Return a rollback dry-run preview as JSON.")
    preview_rollback_parser.add_argument("domain")
    preview_rollback_parser.add_argument("--backup", required=True)
    preview_rollback_parser.set_defaults(command_name="preview-rollback")

    apply_create_parser = subparsers.add_parser("apply-create", help="Execute create and return the result as JSON.")
    apply_create_parser.add_argument("--domain", required=True)
    apply_create_parser.add_argument("--type", required=True, choices=["node", "proxy", "static", "systemd"])
    apply_create_parser.add_argument("--root")
    apply_create_parser.add_argument("--port", type=int)
    apply_create_parser.add_argument("--pm2-name")
    apply_create_parser.add_argument("--service-name")
    apply_create_parser.add_argument("--listen-ipv6", action="store_true")
    apply_create_parser.add_argument("--upstream-host")
    apply_create_parser.add_argument("--alias", action="append", default=[])
    apply_create_parser.add_argument("--ssl-mode", choices=["letsencrypt", "manual"], default="letsencrypt")
    apply_create_parser.add_argument("--ssl-cert")
    apply_create_parser.add_argument("--ssl-key")
    apply_create_parser.add_argument("--email")
    apply_create_parser.add_argument("--force", action="store_true")
    apply_create_parser.set_defaults(command_name="apply-create")

    apply_update_parser = subparsers.add_parser("apply-update", help="Execute update and return the result as JSON.")
    apply_update_parser.add_argument("domain")
    apply_update_parser.add_argument("--type", choices=["node", "proxy", "static", "systemd"])
    apply_update_parser.add_argument("--root")
    apply_update_parser.add_argument("--port", type=int)
    apply_update_parser.add_argument("--pm2-name")
    apply_update_parser.add_argument("--service-name")
    apply_update_parser.add_argument("--listen-ipv6", dest="listen_ipv6", action="store_true")
    apply_update_parser.add_argument("--no-listen-ipv6", dest="listen_ipv6", action="store_false")
    apply_update_parser.add_argument("--upstream-host")
    apply_update_parser.add_argument("--alias", action="append")
    apply_update_parser.add_argument("--clear-aliases", action="store_true")
    apply_update_parser.set_defaults(listen_ipv6=None)
    apply_update_parser.add_argument("--ssl-mode", choices=["letsencrypt", "manual"])
    apply_update_parser.add_argument("--ssl-cert")
    apply_update_parser.add_argument("--ssl-key")
    apply_update_parser.add_argument("--email")
    apply_update_parser.set_defaults(command_name="apply-update")

    apply_remove_parser = subparsers.add_parser("apply-remove", help="Execute remove and return the result as JSON.")
    apply_remove_parser.add_argument("domain")
    apply_remove_parser.set_defaults(command_name="apply-remove")

    apply_reload_parser = subparsers.add_parser("apply-reload", help="Execute reload and return the result as JSON.")
    apply_reload_parser.set_defaults(command_name="apply-reload")

    apply_renew_parser = subparsers.add_parser("apply-renew", help="Execute renew and return the result as JSON.")
    apply_renew_parser.add_argument("domain", nargs="?")
    apply_renew_parser.set_defaults(command_name="apply-renew")

    apply_cert_replace_parser = subparsers.add_parser("apply-cert-replace", help="Execute cert-replace and return the result as JSON.")
    apply_cert_replace_parser.add_argument("domain")
    apply_cert_replace_parser.add_argument("--ssl-cert", required=True)
    apply_cert_replace_parser.add_argument("--ssl-key", required=True)
    apply_cert_replace_parser.set_defaults(command_name="apply-cert-replace")

    apply_import_parser = subparsers.add_parser("apply-import", help="Execute import and return the result as JSON.")
    apply_import_parser.add_argument("--input", required=True)
    apply_import_parser.add_argument("--force", action="store_true")
    apply_import_parser.set_defaults(command_name="apply-import")

    apply_rollback_parser = subparsers.add_parser("apply-rollback", help="Execute rollback and return the result as JSON.")
    apply_rollback_parser.add_argument("domain")
    apply_rollback_parser.add_argument("--backup", required=True)
    apply_rollback_parser.set_defaults(command_name="apply-rollback")

    apply_export_parser = subparsers.add_parser("apply-export", help="Execute export and return the result as JSON.")
    apply_export_parser.add_argument("--output")
    apply_export_parser.set_defaults(command_name="apply-export")

    apply_history_parser = subparsers.add_parser("apply-history", help="Execute history and return the result as JSON.")
    apply_history_parser.add_argument("domain")
    apply_history_parser.set_defaults(command_name="apply-history")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    site_service = build_site_service()

    try:
        if args.command_name == "list":
            payload = site_service.list_sites()
        elif args.command_name == "status":
            payload = site_service.get_status(args.domain)
        elif args.command_name == "cert-info":
            payload = site_service.get_certificate_info(args.domain)
        elif args.command_name == "cert-expiring":
            payload = {
                "days": args.days,
                "items": site_service.list_expiring_certificates(args.days),
            }
        elif args.command_name == "cert-warn":
            items = site_service.list_expiring_certificates(args.days)
            payload = {
                "days": args.days,
                "has_warnings": bool(items),
                "items": items,
            }
        elif args.command_name == "history":
            payload = site_service.list_history(args.domain)
        elif args.command_name == "export":
            payload = site_service.export_sites(args.output)
        elif args.command_name == "healthcheck":
            payload = site_service.run_healthcheck(
                args.domain,
                path=args.path,
                timeout=args.timeout,
                skip_local=args.skip_local,
                skip_remote=args.skip_remote,
                remote_url=args.remote_url,
            )
        elif args.command_name == "cert-verify":
            payload = site_service.verify_certificate(args.domain)
        elif args.command_name == "logs":
            payload = site_service.get_logs(args.domain, args.kind, lines=args.lines)
        elif args.command_name in {"preview-create", "apply-create"}:
            payload = site_service.create_site(
                domain=args.domain,
                site_type=args.type,
                root=args.root,
                port=args.port,
                pm2_name=args.pm2_name,
                service_name=args.service_name,
                email=args.email,
                aliases=args.alias,
                listen_ipv6=args.listen_ipv6,
                upstream_host=args.upstream_host,
                ssl_mode=args.ssl_mode,
                ssl_cert_path=args.ssl_cert,
                ssl_key_path=args.ssl_key,
                force=args.force,
                dry_run=args.command_name == "preview-create",
            )
        elif args.command_name in {"preview-update", "apply-update"}:
            payload = site_service.update_site(
                domain=args.domain,
                site_type=args.type,
                root=args.root,
                port=args.port,
                pm2_name=args.pm2_name,
                service_name=args.service_name,
                email=args.email,
                aliases=args.alias,
                clear_aliases=args.clear_aliases,
                listen_ipv6=args.listen_ipv6,
                upstream_host=args.upstream_host,
                ssl_mode=args.ssl_mode,
                ssl_cert_path=args.ssl_cert,
                ssl_key_path=args.ssl_key,
                dry_run=args.command_name == "preview-update",
            )
        elif args.command_name in {"preview-remove", "apply-remove"}:
            payload = site_service.remove_site(args.domain, dry_run=args.command_name == "preview-remove")
        elif args.command_name in {"preview-reload", "apply-reload"}:
            payload = site_service.reload_nginx(dry_run=args.command_name == "preview-reload")
        elif args.command_name in {"preview-renew", "apply-renew"}:
            payload = site_service.renew_certificates(args.domain, dry_run=args.command_name == "preview-renew")
        elif args.command_name in {"preview-cert-replace", "apply-cert-replace"}:
            payload = site_service.replace_manual_certificate(
                args.domain,
                ssl_cert_path=args.ssl_cert,
                ssl_key_path=args.ssl_key,
                dry_run=args.command_name == "preview-cert-replace",
            )
        elif args.command_name in {"preview-import", "apply-import"}:
            payload = site_service.import_sites(
                args.input,
                force=args.force,
                dry_run=args.command_name == "preview-import",
            )
        elif args.command_name in {"preview-rollback", "apply-rollback"}:
            payload = site_service.rollback_site(
                args.domain,
                args.backup,
                dry_run=args.command_name == "preview-rollback",
            )
        elif args.command_name == "apply-export":
            payload = site_service.export_sites(args.output)
        elif args.command_name == "apply-history":
            payload = site_service.list_history(args.domain)
        else:
            payload = site_service.run_doctor(
                domain=args.domain,
                site_type=args.type,
                port=args.port,
                upstream_host=args.upstream_host,
                listen_ipv6=args.listen_ipv6,
                email=args.email,
                ssl_mode=args.ssl_mode,
            )
    except SiteCtlError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "meta": build_meta(
                        args.command_name,
                        _command_mode(args.command_name),
                        1,
                        trace_id=args.trace_id,
                        request_id=args.request_id,
                    ),
                    "error": str(exc),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1
    if args.command_name == "cert-warn" and payload["has_warnings"]:
        return _emit_response(
            args.command_name,
            payload,
            ok=True,
            exit_code=1,
            trace_id=args.trace_id,
            request_id=args.request_id,
        )
    return _emit_response(
        args.command_name,
        payload,
        ok=True,
        exit_code=0,
        trace_id=args.trace_id,
        request_id=args.request_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
