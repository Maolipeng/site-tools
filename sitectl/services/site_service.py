from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from sitectl.config import SiteCtlConfig
from sitectl.exceptions import (
    CommandExecutionError,
    SiteAlreadyExistsError,
    SiteCtlError,
    SiteNotFoundError,
    StateError,
)
from sitectl.logger import get_logger
from sitectl.models import NginxSiteSnapshot, OperationPreview, SiteListing, SiteRecord, SiteStatus, SiteType
from sitectl.models import BackupEntry, CertificateInfo, CertificateSummary, CertificateVerification, DoctorReport, HealthcheckReport, LogResult, SslMode
from sitectl.services.certificate_service import CertificateService
from sitectl.services.certbot_service import CertbotService
from sitectl.services.doctor_service import DoctorService
from sitectl.services.healthcheck_service import HealthcheckService
from sitectl.services.log_service import LogService
from sitectl.services.nginx_service import NginxService
from sitectl.services.pm2_service import PM2Service
from sitectl.services.status_service import StatusService
from sitectl.services.systemd_service import SystemdService
from sitectl.utils import atomic_write_json, load_json
from sitectl.validators import validate_aliases, validate_create_options, validate_domain, validate_ssl_mode, validate_upstream_host


LOGGER = get_logger(__name__)


class SiteService:
    def __init__(
        self,
        config: SiteCtlConfig,
        nginx_service: NginxService,
        certbot_service: CertbotService,
        pm2_service: PM2Service,
        status_service: StatusService,
        log_service: LogService | None = None,
        doctor_service: DoctorService | None = None,
        systemd_service: SystemdService | None = None,
        healthcheck_service: HealthcheckService | None = None,
        certificate_service: CertificateService | None = None,
    ) -> None:
        self.config = config
        self.nginx_service = nginx_service
        self.certbot_service = certbot_service
        self.pm2_service = pm2_service
        self.status_service = status_service
        self.log_service = log_service
        self.doctor_service = doctor_service
        self.systemd_service = systemd_service
        self.healthcheck_service = healthcheck_service
        self.certificate_service = certificate_service

    def _load_records(self) -> list[SiteRecord]:
        try:
            payload = load_json(self.config.state_file)
        except FileNotFoundError:
            return []
        except StateError:
            raise
        sites = payload.get("sites", [])
        if not isinstance(sites, list):
            raise StateError(f"Invalid state file structure: {self.config.state_file}")
        return [SiteRecord.from_dict(item) for item in sites if isinstance(item, dict)]

    def _save_records(self, records: list[SiteRecord]) -> None:
        atomic_write_json(self.config.state_file, {"sites": [record.to_dict() for record in records]})

    def _find_record(self, domain: str) -> SiteRecord | None:
        normalized = validate_domain(domain)
        for record in self._load_records():
            if record.domain == normalized:
                return record
        return None

    def _normalize_fields(
        self,
        *,
        site_type: SiteType,
        root: str | None,
        port: int | None,
        pm2_name: str | None,
        service_name: str | None,
        upstream_host: str | None,
    ) -> tuple[str | None, int | None, str | None, str | None, str | None]:
        if site_type is SiteType.NODE:
            return root, port, pm2_name, None, validate_upstream_host(upstream_host)
        if site_type is SiteType.SYSTEMD:
            return None, port, None, service_name, validate_upstream_host(upstream_host)
        if site_type is SiteType.PROXY:
            return None, port, None, None, validate_upstream_host(upstream_host)
        return root, None, None, None, None

    def _build_record(
        self,
        *,
        domain: str,
        site_type: str,
        root: str | None,
        port: int | None,
        pm2_name: str | None,
        service_name: str | None,
        email: str | None,
        aliases: list[str] | None,
        listen_ipv6: bool,
        upstream_host: str | None,
        ssl_mode: str | None,
        ssl_cert_path: str | None,
        ssl_key_path: str | None,
        existing_record: SiteRecord | None = None,
    ) -> SiteRecord:
        normalized_domain = validate_domain(domain)
        normalized_aliases = validate_aliases(aliases, normalized_domain)
        normalized_ssl_mode = validate_ssl_mode(ssl_mode)
        normalized_type = validate_create_options(
            domain=normalized_domain,
            site_type=site_type,
            root=root,
            port=port,
            pm2_name=pm2_name,
            service_name=service_name,
            email=email,
            aliases=normalized_aliases,
            upstream_host=upstream_host,
            ssl_mode=normalized_ssl_mode.value,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path,
        )
        root, port, pm2_name, service_name, upstream_host = self._normalize_fields(
            site_type=normalized_type,
            root=str(Path(root)) if root else None,
            port=port,
            pm2_name=pm2_name,
            service_name=service_name,
            upstream_host=upstream_host,
        )
        return SiteRecord(
            domain=normalized_domain,
            type=normalized_type,
            ssl_mode=normalized_ssl_mode,
            listen_ipv6=listen_ipv6,
            upstream_host=upstream_host,
            aliases=normalized_aliases,
            root=root,
            port=port,
            pm2_name=pm2_name,
            service_name=service_name,
            ssl_cert_path=ssl_cert_path if normalized_ssl_mode is SslMode.MANUAL else None,
            ssl_key_path=ssl_key_path if normalized_ssl_mode is SslMode.MANUAL else None,
            email=email,
            created_at=existing_record.created_at if existing_record else "",
        )

    def _render_preview(
        self,
        *,
        title: str,
        actions: Iterable[str],
        record: SiteRecord | None = None,
    ) -> OperationPreview:
        config_path = None
        config_content = None
        if record is not None:
            config_path = str(self.nginx_service.config_path(record.domain))
            config_content = self.nginx_service.render_config(record)
        return OperationPreview(title=title, actions=list(actions), config_path=config_path, config_content=config_content)

    def _rollback_site(
        self,
        *,
        snapshot: NginxSiteSnapshot,
        previous_record: SiteRecord | None,
        current_record: SiteRecord,
        cleanup_pm2_name: str | None,
        restore_previous_pm2: bool,
        cleanup_systemd_name: str | None,
        restore_previous_systemd: bool,
    ) -> None:
        try:
            self.nginx_service.restore_snapshot(snapshot)
            if cleanup_pm2_name:
                try:
                    self.pm2_service.delete_process(cleanup_pm2_name)
                except CommandExecutionError as exc:
                    LOGGER.warning("Failed to cleanup PM2 process %s during rollback: %s", cleanup_pm2_name, exc)
            if restore_previous_pm2 and previous_record and previous_record.pm2_name and previous_record.root and previous_record.port:
                try:
                    self.pm2_service.start_or_restart(
                        previous_record.pm2_name,
                        Path(previous_record.root),
                        previous_record.port,
                    )
                except SiteCtlError as exc:
                    LOGGER.warning("Failed to restore PM2 process %s during rollback: %s", previous_record.pm2_name, exc)
            if cleanup_systemd_name:
                try:
                    self.systemd_service.stop_service(cleanup_systemd_name)
                except SiteCtlError as exc:
                    LOGGER.warning("Failed to cleanup systemd service %s during rollback: %s", cleanup_systemd_name, exc)
            if restore_previous_systemd and previous_record and previous_record.service_name:
                try:
                    self.systemd_service.restart_service(previous_record.service_name)
                except SiteCtlError as exc:
                    LOGGER.warning("Failed to restore systemd service %s during rollback: %s", previous_record.service_name, exc)
            self.nginx_service.validate_nginx_config()
            self.nginx_service.reload_nginx(validate_first=False)
        except SiteCtlError as exc:
            LOGGER.warning("Rollback failed for %s: %s", current_record.domain, exc)

    def _start_runtime_for_record(self, record: SiteRecord | None) -> None:
        if not record:
            return
        if record.type is SiteType.NODE and record.root and record.pm2_name and record.port is not None:
            self.pm2_service.start_or_restart(record.pm2_name, Path(record.root), record.port)
        elif record.type is SiteType.SYSTEMD and record.service_name:
            self.systemd_service.restart_service(record.service_name)

    def _stop_runtime_for_record(self, record: SiteRecord | None) -> None:
        if not record:
            return
        if record.type is SiteType.NODE and record.pm2_name:
            self.pm2_service.delete_process(record.pm2_name)
        elif record.type is SiteType.SYSTEMD and record.service_name:
            self.systemd_service.stop_service(record.service_name)

    def _transition_runtime(self, current_record: SiteRecord | None, target_record: SiteRecord | None) -> None:
        if current_record and current_record.type is SiteType.NODE and current_record.pm2_name:
            same_target_pm2 = (
                target_record
                and target_record.type is SiteType.NODE
                and target_record.pm2_name == current_record.pm2_name
            )
            if not same_target_pm2:
                self.pm2_service.delete_process(current_record.pm2_name)

        if current_record and current_record.type is SiteType.SYSTEMD and current_record.service_name:
            same_target_service = (
                target_record
                and target_record.type is SiteType.SYSTEMD
                and target_record.service_name == current_record.service_name
            )
            if not same_target_service:
                self.systemd_service.stop_service(current_record.service_name)

        self._start_runtime_for_record(target_record)

    def _preview_create_or_update(
        self,
        *,
        action: str,
        record: SiteRecord,
        previous_record: SiteRecord | None = None,
        force: bool = False,
    ) -> OperationPreview:
        actions: list[str] = []
        config_path = self.nginx_service.config_path(record.domain)
        if config_path.exists():
            if force or action == "update":
                actions.append(f"backup existing Nginx config to {config_path}.bak.<timestamp>")
            else:
                actions.append(f"refuse to overwrite existing Nginx config at {config_path}")
        if record.aliases:
            actions.append(f"configure server aliases: {', '.join(record.aliases)}")
        if record.listen_ipv6:
            actions.append("add explicit IPv6 listen directives for Nginx")
            if record.ssl_mode is SslMode.LETSENCRYPT:
                actions.append(f"verify AAAA for {record.domain} points at this host before requesting Let's Encrypt over IPv6")
        if record.upstream_host and record.type in {SiteType.NODE, SiteType.PROXY, SiteType.SYSTEMD}:
            actions.append(f"use upstream host {record.upstream_host} for local proxy and health checks")
        if record.ssl_mode is SslMode.MANUAL and record.ssl_cert_path and record.ssl_key_path:
            actions.append(f"use manual TLS certificate {record.ssl_cert_path}")
            actions.append(f"use manual TLS private key {record.ssl_key_path}")
        if record.type is SiteType.NODE and record.root and record.pm2_name and record.port is not None:
            package_manager = self.pm2_service.package_manager(Path(record.root))
            actions.append(f"run {package_manager} install in {record.root}")
            actions.append(f"run {package_manager} run build in {record.root} if package.json defines a build script")
            if previous_record and previous_record.type is SiteType.NODE and previous_record.pm2_name == record.pm2_name:
                actions.append(f"restart PM2 process {record.pm2_name} with PORT={record.port}")
            else:
                actions.append(f"start PM2 process {record.pm2_name} with PORT={record.port}")
        if record.type is SiteType.SYSTEMD and record.service_name:
            actions.append(f"restart systemd service {record.service_name}")
        actions.extend(
            [
                f"write Nginx config to {config_path}",
                f"ensure enabled symlink at {self.nginx_service.enabled_path(record.domain)}",
                "run nginx -t",
                "reload Nginx",
                f"update local state file {self.config.state_file}",
            ]
        )
        if record.ssl_mode is SslMode.LETSENCRYPT:
            actions.insert(
                -1,
                f"request or refresh Let's Encrypt certificate for {', '.join([record.domain, *(record.aliases or [])])}",
            )
        if previous_record and previous_record.type is SiteType.NODE and (
            record.type is not SiteType.NODE or previous_record.pm2_name != record.pm2_name
        ):
            actions.append(f"delete old PM2 process {previous_record.pm2_name} after successful update")
        if previous_record and previous_record.type is SiteType.SYSTEMD and (
            record.type is not SiteType.SYSTEMD or previous_record.service_name != record.service_name
        ):
            actions.append(f"stop old systemd service {previous_record.service_name} after successful update")
        return self._render_preview(title=f"{action.title()} site {record.domain}", actions=actions, record=record)

    def _warn_if_ipv6_https_not_ready(self, record: SiteRecord) -> None:
        if not self.doctor_service:
            return
        if record.ssl_mode is not SslMode.LETSENCRYPT or not record.listen_ipv6:
            return
        report = self.doctor_service.run(
            domain=record.domain,
            site_type=record.type.value,
            port=record.port,
            upstream_host=record.upstream_host,
            listen_ipv6=record.listen_ipv6,
            email=record.email,
            ssl_mode=record.ssl_mode.value,
        )
        dns_check_name = f"dns:aaaa:{record.domain}"
        for check in report.checks:
            if check.name in {"network:global-ipv6", dns_check_name} and not check.ok:
                LOGGER.warning("IPv6 HTTPS readiness warning for %s: %s", record.domain, check.detail)
        for item in report.advice or []:
            if item.level in {"warning", "critical"}:
                LOGGER.warning("IPv6 HTTPS advice for %s: %s", record.domain, item.detail)

    def create_site(
        self,
        *,
        domain: str,
        site_type: str,
        root: str | None,
        port: int | None,
        pm2_name: str | None,
        service_name: str | None,
        email: str | None,
        aliases: list[str] | None = None,
        listen_ipv6: bool = False,
        upstream_host: str | None = None,
        ssl_mode: str | None = None,
        ssl_cert_path: str | None = None,
        ssl_key_path: str | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> SiteRecord | OperationPreview:
        normalized_domain = validate_domain(domain)
        existing_record = self._find_record(normalized_domain)
        config_path = self.nginx_service.config_path(normalized_domain)
        if not force:
            if existing_record:
                raise SiteAlreadyExistsError(f"Site already exists in state: {normalized_domain}. Use 'sitectl status {normalized_domain}' to inspect it or pass --force to overwrite the Nginx config.")
            if config_path.exists():
                raise SiteAlreadyExistsError(
                    f"Nginx config already exists for {normalized_domain} at {config_path}, but no matching state record was found. "
                    f"Use 'sitectl status {normalized_domain}' to inspect it or pass --force to adopt and overwrite the existing config."
                )

        record = self._build_record(
            domain=normalized_domain,
            site_type=site_type,
            root=root,
            port=port,
            pm2_name=pm2_name,
            service_name=service_name,
            email=email,
            aliases=aliases,
            listen_ipv6=listen_ipv6,
            upstream_host=upstream_host,
            ssl_mode=ssl_mode,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path,
            existing_record=None,
        )
        if dry_run:
            return self._preview_create_or_update(action="create", record=record, force=force)

        snapshot = self.nginx_service.snapshot_site(normalized_domain)
        cleanup_pm2_name: str | None = None
        cleanup_systemd_name: str | None = None
        try:
            if record.type is SiteType.NODE and record.root and record.pm2_name and record.port is not None:
                root_path = Path(record.root)
                self.pm2_service.install_dependencies(root_path)
                self.pm2_service.build_if_present(root_path)
                self.pm2_service.start_or_restart(record.pm2_name, root_path, record.port)
                cleanup_pm2_name = record.pm2_name
            if record.type is SiteType.SYSTEMD and record.service_name:
                self.systemd_service.restart_service(record.service_name)
                cleanup_systemd_name = record.service_name

            self.nginx_service.write_config(
                record,
                force=force,
                backup_metadata=existing_record.to_dict() if existing_record else None,
            )
            self.nginx_service.enable_site(normalized_domain)
            self.nginx_service.validate_nginx_config()
            self.nginx_service.reload_nginx(validate_first=False)
            if record.ssl_mode is SslMode.LETSENCRYPT:
                self._warn_if_ipv6_https_not_ready(record)
                self.certbot_service.request_certificate([normalized_domain, *(record.aliases or [])], email or "")

            records = [item for item in self._load_records() if item.domain != normalized_domain]
            records.append(record)
            self._save_records(records)
            return record
        except SiteCtlError:
            self._rollback_site(
                snapshot=snapshot,
                previous_record=None,
                current_record=record,
                cleanup_pm2_name=cleanup_pm2_name,
                restore_previous_pm2=False,
                cleanup_systemd_name=cleanup_systemd_name,
                restore_previous_systemd=False,
            )
            raise

    def update_site(
        self,
        *,
        domain: str,
        site_type: str | None,
        root: str | None,
        port: int | None,
        pm2_name: str | None,
        service_name: str | None,
        email: str | None,
        aliases: list[str] | None = None,
        clear_aliases: bool = False,
        listen_ipv6: bool | None = None,
        upstream_host: str | None = None,
        ssl_mode: str | None = None,
        ssl_cert_path: str | None = None,
        ssl_key_path: str | None = None,
        dry_run: bool = False,
    ) -> SiteRecord | OperationPreview:
        normalized_domain = validate_domain(domain)
        existing_record = self._find_record(normalized_domain)
        if not existing_record:
            raise SiteNotFoundError(f"Site not found: {normalized_domain}")

        merged_type = site_type or existing_record.type.value
        merged_ssl_mode = validate_ssl_mode(ssl_mode).value if ssl_mode else existing_record.ssl_mode.value
        merged_root = root if root is not None else existing_record.root
        merged_port = port if port is not None else existing_record.port
        merged_pm2_name = pm2_name if pm2_name is not None else existing_record.pm2_name
        merged_service_name = service_name if service_name is not None else existing_record.service_name
        merged_email = email if email is not None else existing_record.email
        merged_aliases = [] if clear_aliases else (aliases if aliases is not None else existing_record.aliases)
        merged_listen_ipv6 = listen_ipv6 if listen_ipv6 is not None else existing_record.listen_ipv6
        merged_upstream_host = upstream_host if upstream_host is not None else existing_record.upstream_host
        merged_ssl_cert_path = ssl_cert_path if ssl_cert_path is not None else existing_record.ssl_cert_path
        merged_ssl_key_path = ssl_key_path if ssl_key_path is not None else existing_record.ssl_key_path
        record = self._build_record(
            domain=normalized_domain,
            site_type=merged_type,
            root=merged_root,
            port=merged_port,
            pm2_name=merged_pm2_name,
            service_name=merged_service_name,
            email=merged_email,
            aliases=merged_aliases,
            listen_ipv6=merged_listen_ipv6,
            upstream_host=merged_upstream_host,
            ssl_mode=merged_ssl_mode,
            ssl_cert_path=merged_ssl_cert_path,
            ssl_key_path=merged_ssl_key_path,
            existing_record=existing_record,
        )

        if dry_run:
            return self._preview_create_or_update(
                action="update",
                record=record,
                previous_record=existing_record,
                force=True,
            )

        snapshot = self.nginx_service.snapshot_site(normalized_domain)
        cleanup_pm2_name: str | None = None
        restore_previous_pm2 = False
        cleanup_systemd_name: str | None = None
        restore_previous_systemd = False

        try:
            if record.type is SiteType.NODE and record.root and record.pm2_name and record.port is not None:
                root_path = Path(record.root)
                self.pm2_service.npm_install(root_path)
                self.pm2_service.build_if_present(root_path)
                self.pm2_service.start_or_restart(record.pm2_name, root_path, record.port)
                if existing_record.type is SiteType.NODE and existing_record.pm2_name == record.pm2_name:
                    restore_previous_pm2 = True
                else:
                    cleanup_pm2_name = record.pm2_name
            if record.type is SiteType.SYSTEMD and record.service_name:
                self.systemd_service.restart_service(record.service_name)
                if existing_record.type is SiteType.SYSTEMD and existing_record.service_name == record.service_name:
                    restore_previous_systemd = True
                else:
                    cleanup_systemd_name = record.service_name

            self.nginx_service.write_config(
                record,
                force=True,
                backup_metadata=existing_record.to_dict() if existing_record else None,
            )
            self.nginx_service.enable_site(normalized_domain)
            self.nginx_service.validate_nginx_config()
            self.nginx_service.reload_nginx(validate_first=False)
            if record.ssl_mode is SslMode.LETSENCRYPT:
                self._warn_if_ipv6_https_not_ready(record)
                self.certbot_service.request_certificate([normalized_domain, *(record.aliases or [])], record.email or "")

            records = [item for item in self._load_records() if item.domain != normalized_domain]
            records.append(record)
            self._save_records(records)

            delete_previous_pm2_after_success = existing_record.type is SiteType.NODE and (
                record.type is not SiteType.NODE or existing_record.pm2_name != record.pm2_name
            )
            if delete_previous_pm2_after_success and existing_record.pm2_name:
                try:
                    self.pm2_service.delete_process(existing_record.pm2_name)
                except CommandExecutionError as exc:
                    LOGGER.warning("Failed to delete old PM2 process %s: %s", existing_record.pm2_name, exc)
            stop_previous_systemd_after_success = existing_record.type is SiteType.SYSTEMD and (
                record.type is not SiteType.SYSTEMD or existing_record.service_name != record.service_name
            )
            if stop_previous_systemd_after_success and existing_record.service_name:
                try:
                    self.systemd_service.stop_service(existing_record.service_name)
                except CommandExecutionError as exc:
                    LOGGER.warning("Failed to stop old systemd service %s: %s", existing_record.service_name, exc)
            return record
        except SiteCtlError:
            self._rollback_site(
                snapshot=snapshot,
                previous_record=existing_record,
                current_record=record,
                cleanup_pm2_name=cleanup_pm2_name,
                restore_previous_pm2=restore_previous_pm2,
                cleanup_systemd_name=cleanup_systemd_name,
                restore_previous_systemd=restore_previous_systemd,
            )
            raise

    def remove_site(self, domain: str, dry_run: bool = False) -> str | OperationPreview:
        normalized_domain = validate_domain(domain)
        record = self._find_record(normalized_domain)

        config_exists = self.nginx_service.config_path(normalized_domain).exists()
        enabled_path = self.nginx_service.enabled_path(normalized_domain)
        enabled_exists = enabled_path.exists() or enabled_path.is_symlink()
        if not record and not config_exists and not enabled_exists:
            raise SiteNotFoundError(f"Site not found: {normalized_domain}")

        if dry_run:
            actions = [
                f"remove enabled symlink {self.nginx_service.enabled_path(normalized_domain)} if it exists",
                f"remove Nginx config {self.nginx_service.config_path(normalized_domain)} if it exists",
                "run nginx -t",
                "reload Nginx",
                f"remove {normalized_domain} from local state file {self.config.state_file}",
            ]
            if record and record.type is SiteType.NODE and record.pm2_name:
                actions.insert(0, f"delete PM2 process {record.pm2_name} if it exists")
            if record and record.type is SiteType.SYSTEMD and record.service_name:
                actions.insert(0, f"stop systemd service {record.service_name} if it exists")
            return self._render_preview(title=f"Remove site {normalized_domain}", actions=actions)

        if record and record.type is SiteType.NODE and record.pm2_name:
            try:
                self.pm2_service.delete_process(record.pm2_name)
            except CommandExecutionError as exc:
                LOGGER.warning("Failed to delete PM2 process %s: %s", record.pm2_name, exc)
        if record and record.type is SiteType.SYSTEMD and record.service_name:
            try:
                self.systemd_service.stop_service(record.service_name)
            except CommandExecutionError as exc:
                LOGGER.warning("Failed to stop systemd service %s: %s", record.service_name, exc)

        self.nginx_service.disable_site(normalized_domain)
        self.nginx_service.remove_config(normalized_domain)
        self.nginx_service.validate_nginx_config()
        self.nginx_service.reload_nginx(validate_first=False)

        if record:
            remaining = [item for item in self._load_records() if item.domain != normalized_domain]
            self._save_records(remaining)
        return normalized_domain

    def list_sites(self) -> list[SiteListing]:
        try:
            records = self._load_records()
        except StateError:
            records = []

        if records:
            return [SiteListing(domain=record.domain, type=record.type.value) for record in records]

        return [SiteListing(domain=domain, type="unknown") for domain in self.nginx_service.list_available_domains()]

    def get_status(self, domain: str) -> SiteStatus:
        normalized_domain = validate_domain(domain)
        return self.status_service.get_status(normalized_domain, self._find_record(normalized_domain))

    def get_logs(self, domain: str, kind: str, lines: int = 100) -> LogResult:
        normalized_domain = validate_domain(domain)
        record = self._find_record(normalized_domain)
        if kind == "access":
            return self.log_service.read_nginx_access_log(
                self.config.log_dir / f"{normalized_domain}.access.log",
                lines,
            )
        if kind == "error":
            return self.log_service.read_nginx_error_log(
                self.config.log_dir / f"{normalized_domain}.error.log",
                lines,
            )
        if kind == "pm2":
            if not record or record.type is not SiteType.NODE or not record.pm2_name:
                raise SiteNotFoundError(f"No PM2 process configured for {normalized_domain}")
            return self.log_service.read_pm2_log(record.pm2_name, lines)
        if kind == "systemd":
            if not record or record.type is not SiteType.SYSTEMD or not record.service_name:
                raise SiteNotFoundError(f"No systemd service configured for {normalized_domain}")
            return self.log_service.read_systemd_log(record.service_name, lines)
        raise SiteCtlError(f"Unsupported log kind: {kind}")

    def run_doctor(
        self,
        *,
        domain: str | None = None,
        site_type: str | None = None,
        port: int | None = None,
        upstream_host: str | None = None,
        listen_ipv6: bool = False,
        email: str | None = None,
        ssl_mode: str = "letsencrypt",
    ) -> DoctorReport:
        normalized_domain = validate_domain(domain) if domain else None
        return self.doctor_service.run(
            domain=normalized_domain,
            site_type=site_type,
            port=port,
            upstream_host=upstream_host,
            listen_ipv6=listen_ipv6,
            email=email,
            ssl_mode=ssl_mode,
        )

    def get_certificate_info(self, domain: str) -> CertificateInfo:
        normalized_domain = validate_domain(domain)
        record = self._find_record(normalized_domain)
        if not record:
            raise SiteNotFoundError(f"Site not found: {normalized_domain}")
        return self.certificate_service.inspect_certificate(record)

    def list_expiring_certificates(self, days: int = 30) -> list[CertificateSummary]:
        return self.certificate_service.find_expiring(self._load_records(), days)

    def verify_certificate(self, domain: str) -> CertificateVerification:
        normalized_domain = validate_domain(domain)
        record = self._find_record(normalized_domain)
        if not record:
            raise SiteNotFoundError(f"Site not found: {normalized_domain}")
        return self.certificate_service.verify_certificate_pair(record)

    def replace_manual_certificate(
        self,
        domain: str,
        *,
        ssl_cert_path: str,
        ssl_key_path: str,
        dry_run: bool = False,
    ) -> SiteRecord | OperationPreview:
        normalized_domain = validate_domain(domain)
        record = self._find_record(normalized_domain)
        if not record:
            raise SiteNotFoundError(f"Site not found: {normalized_domain}")
        if record.ssl_mode is not SslMode.MANUAL:
            raise SiteCtlError(f"Site {normalized_domain} is not using manual certificates.")
        return self.update_site(
            domain=normalized_domain,
            site_type=None,
            root=None,
            port=None,
            pm2_name=None,
            service_name=None,
            email=None,
            aliases=None,
            listen_ipv6=None,
            upstream_host=None,
            ssl_mode=SslMode.MANUAL.value,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path,
            dry_run=dry_run,
        )

    def export_sites(self, output_path: str | None = None) -> str:
        records = self._load_records()
        bundle = {
            "sites": [record.to_dict() for record in records],
            "nginx_configs": {
                record.domain: self.nginx_service.config_path(record.domain).read_text(encoding="utf-8")
                for record in records
                if self.nginx_service.config_path(record.domain).exists()
            },
        }
        serialized = json.dumps(bundle, indent=2, sort_keys=True)
        if output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(serialized + "\n", encoding="utf-8")
            return str(target)
        return serialized

    def import_sites(self, input_path: str, *, force: bool = False, dry_run: bool = False) -> str | OperationPreview:
        payload = load_json(Path(input_path))
        raw_sites = payload.get("sites", [])
        nginx_configs = payload.get("nginx_configs", {})
        if not isinstance(raw_sites, list):
            raise StateError(f"Invalid import bundle format: {input_path}")
        records = [SiteRecord.from_dict(item) for item in raw_sites if isinstance(item, dict)]

        actions: list[str] = []
        for record in records:
            validate_domain(record.domain)
            validate_aliases(record.aliases, record.domain)
            config_path = self.nginx_service.config_path(record.domain)
            if config_path.exists():
                if not force:
                    raise SiteAlreadyExistsError(f"Site already exists: {record.domain}")
                actions.append(f"backup existing Nginx config to {config_path}.bak.<timestamp>")
            actions.append(f"restore Nginx config for {record.domain}")
            actions.append(f"ensure enabled symlink for {record.domain}")
        actions.extend(["run nginx -t", "reload Nginx", f"merge imported state into {self.config.state_file}"])

        if dry_run:
            return self._render_preview(title=f"Import sites from {input_path}", actions=actions)

        previous_records = self._load_records()
        snapshots = {record.domain: self.nginx_service.snapshot_site(record.domain) for record in records}
        try:
            for record in records:
                content = nginx_configs.get(record.domain) or self.nginx_service.render_config(record)
                previous_record = next((item for item in previous_records if item.domain == record.domain), None)
                self.nginx_service.write_config_text(
                    record.domain,
                    str(content),
                    force=force,
                    backup_metadata=previous_record.to_dict() if previous_record else None,
                )
                self.nginx_service.enable_site(record.domain)
            self.nginx_service.validate_nginx_config()
            self.nginx_service.reload_nginx(validate_first=False)
            merged_records = [item for item in previous_records if item.domain not in {record.domain for record in records}]
            merged_records.extend(records)
            self._save_records(merged_records)
            return f"Imported {len(records)} site(s) from {input_path}"
        except SiteCtlError:
            for snapshot in snapshots.values():
                self.nginx_service.restore_snapshot(snapshot)
            self._save_records(previous_records)
            try:
                self.nginx_service.validate_nginx_config()
                self.nginx_service.reload_nginx(validate_first=False)
            except SiteCtlError as exc:
                LOGGER.warning("Import rollback failed: %s", exc)
            raise

    def run_healthcheck(
        self,
        domain: str,
        *,
        path: str = "/",
        timeout: float = 5.0,
        skip_local: bool = False,
        skip_remote: bool = False,
        remote_url: str | None = None,
    ) -> HealthcheckReport:
        normalized_domain = validate_domain(domain)
        record = self._find_record(normalized_domain)
        if not record:
            raise SiteNotFoundError(f"Site not found: {normalized_domain}")
        return self.healthcheck_service.run(
            record=record,
            path=path,
            timeout=timeout,
            skip_local=skip_local,
            skip_remote=skip_remote,
            remote_url=remote_url,
        )

    def list_history(self, domain: str) -> list[BackupEntry]:
        normalized_domain = validate_domain(domain)
        return self.nginx_service.list_backups(normalized_domain)

    def rollback_site(self, domain: str, backup_name: str, dry_run: bool = False) -> str | OperationPreview:
        normalized_domain = validate_domain(domain)
        normalized_backup = backup_name if backup_name.startswith(f"{normalized_domain}.bak.") else f"{normalized_domain}.bak.{backup_name}"
        backup_path = self.config.nginx_available_dir / normalized_backup
        metadata_path = backup_path.with_name(f"{backup_path.name}.meta.json")
        if not backup_path.exists():
            raise SiteNotFoundError(f"Backup not found: {normalized_backup}")

        actions = [
            f"backup current config for {normalized_domain}",
            f"restore Nginx config from {backup_path}",
            f"ensure enabled symlink at {self.nginx_service.enabled_path(normalized_domain)}",
            "run nginx -t",
            "reload Nginx",
        ]
        if metadata_path.exists():
            actions.append(f"restore state record for {normalized_domain} from {metadata_path}")
            metadata_record = SiteRecord.from_dict(load_json(metadata_path))
            if current_record := self._find_record(normalized_domain):
                if current_record.type is SiteType.NODE and current_record.pm2_name:
                    same_pm2 = metadata_record.type is SiteType.NODE and metadata_record.pm2_name == current_record.pm2_name
                    if not same_pm2:
                        actions.append(f"delete current PM2 process {current_record.pm2_name}")
                if current_record.type is SiteType.SYSTEMD and current_record.service_name:
                    same_service = metadata_record.type is SiteType.SYSTEMD and metadata_record.service_name == current_record.service_name
                    if not same_service:
                        actions.append(f"stop current systemd service {current_record.service_name}")
            if metadata_record.type is SiteType.NODE and metadata_record.pm2_name and metadata_record.root and metadata_record.port is not None:
                actions.append(f"restore PM2 process {metadata_record.pm2_name} with PORT={metadata_record.port}")
            if metadata_record.type is SiteType.SYSTEMD and metadata_record.service_name:
                actions.append(f"restart systemd service {metadata_record.service_name}")
        if dry_run:
            return self._render_preview(title=f"Rollback site {normalized_domain}", actions=actions)

        current_record = self._find_record(normalized_domain)
        previous_records = self._load_records()
        snapshot = self.nginx_service.snapshot_site(normalized_domain)
        metadata_record: SiteRecord | None = None
        if metadata_path.exists():
            metadata_record = SiteRecord.from_dict(load_json(metadata_path))

        try:
            if snapshot.config_exists and snapshot.config_content is not None:
                self.nginx_service.create_backup(normalized_domain, metadata=current_record.to_dict() if current_record else None)
            restored_content = backup_path.read_text(encoding="utf-8")
            config_path = self.nginx_service.config_path(normalized_domain)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(restored_content, encoding="utf-8")
            self.nginx_service.enable_site(normalized_domain)
            if metadata_record:
                merged_records = [item for item in previous_records if item.domain != normalized_domain]
                merged_records.append(metadata_record)
                self._save_records(merged_records)
                self._transition_runtime(current_record, metadata_record)
            self.nginx_service.validate_nginx_config()
            self.nginx_service.reload_nginx(validate_first=False)
            return f"Rolled back {normalized_domain} using {normalized_backup}"
        except SiteCtlError:
            self.nginx_service.restore_snapshot(snapshot)
            self._save_records(previous_records)
            try:
                self._transition_runtime(metadata_record, current_record)
            except SiteCtlError as exc:
                LOGGER.warning("Rollback runtime restore failed: %s", exc)
            try:
                self.nginx_service.validate_nginx_config()
                self.nginx_service.reload_nginx(validate_first=False)
            except SiteCtlError as exc:
                LOGGER.warning("Rollback restore failed: %s", exc)
            raise

    def reload_nginx(self, dry_run: bool = False) -> str | OperationPreview:
        if dry_run:
            return self._render_preview(
                title="Reload Nginx",
                actions=["run nginx -t", "reload Nginx"],
            )
        self.nginx_service.validate_nginx_config()
        self.nginx_service.reload_nginx(validate_first=False)
        return "nginx"

    def renew_certificates(self, domain: str | None = None, dry_run: bool = False) -> str | OperationPreview:
        if domain:
            validate_domain(domain)
            record = self._find_record(domain)
            if record and record.ssl_mode is SslMode.MANUAL:
                raise SiteCtlError(f"Site {domain} uses manual certificates and does not support certbot renew.")
        if dry_run:
            actions = ["run certbot renew" if not domain else f"run certbot renew --cert-name {domain}", "run nginx -t", "reload Nginx"]
            return self._render_preview(title=f"Renew certificates for {domain or 'all'}", actions=actions)
        self.certbot_service.renew(domain)
        self.nginx_service.validate_nginx_config()
        self.nginx_service.reload_nginx(validate_first=False)
        return domain or "all"

    def get_record(self, domain: str) -> SiteRecord | None:
        return self._find_record(domain)
