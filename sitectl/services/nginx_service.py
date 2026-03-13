from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sitectl.config import SiteCtlConfig
from sitectl.exceptions import CommandExecutionError, NginxConfigError, SiteAlreadyExistsError, SiteNotFoundError
from sitectl.models import BackupEntry, NginxSiteSnapshot, SiteRecord, SiteType, SslMode
from sitectl.services.system_service import SystemService
from sitectl.utils import backup_suffix, read_text, render_template


class NginxService:
    def __init__(self, config: SiteCtlConfig, system_service: SystemService) -> None:
        self.config = config
        self.system_service = system_service

    def config_path(self, domain: str) -> Path:
        return self.config.nginx_available_dir / domain

    def enabled_path(self, domain: str) -> Path:
        return self.config.nginx_enabled_dir / domain

    def template_path(self, site_type: SiteType) -> Path:
        mapping = {
            SiteType.NODE: "nginx_node.conf.j2",
            SiteType.PROXY: "nginx_proxy.conf.j2",
            SiteType.STATIC: "nginx_static.conf.j2",
            SiteType.SYSTEMD: "nginx_proxy.conf.j2",
        }
        return self.config.templates_dir / mapping[site_type]

    def ssl_template_path(self, site_type: SiteType) -> Path:
        mapping = {
            SiteType.NODE: "nginx_node_ssl.conf.j2",
            SiteType.PROXY: "nginx_proxy_ssl.conf.j2",
            SiteType.STATIC: "nginx_static_ssl.conf.j2",
            SiteType.SYSTEMD: "nginx_proxy_ssl.conf.j2",
        }
        return self.config.templates_dir / mapping[site_type]

    def render_config(self, record: SiteRecord) -> str:
        template_path = self.ssl_template_path(record.type) if record.ssl_mode is SslMode.MANUAL else self.template_path(record.type)
        template = read_text(template_path)
        context = {
            "domain": record.domain,
            "server_names": " ".join([record.domain, *(record.aliases or [])]),
            "port": record.port or "",
            "root": record.root or "",
            "ssl_cert_path": record.ssl_cert_path or "",
            "ssl_key_path": record.ssl_key_path or "",
            "access_log": self.config.log_dir / f"{record.domain}.access.log",
            "error_log": self.config.log_dir / f"{record.domain}.error.log",
        }
        return render_template(template, context)

    def write_config(
        self,
        record: SiteRecord,
        force: bool = False,
        backup_metadata: dict[str, object] | None = None,
    ) -> Path:
        return self.write_config_text(
            record.domain,
            self.render_config(record),
            force=force,
            backup_metadata=backup_metadata,
        )

    def create_backup(self, domain: str, metadata: dict[str, object] | None = None) -> Path:
        target = self.config_path(domain)
        if not target.exists():
            raise SiteNotFoundError(f"Nginx config does not exist for {domain}")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        backup_path = target.with_name(f"{target.name}{backup_suffix(timestamp)}")
        shutil.copy2(target, backup_path)
        if metadata is not None:
            backup_path.with_name(f"{backup_path.name}.meta.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return backup_path

    def write_config_text(
        self,
        domain: str,
        content: str,
        force: bool = False,
        backup_metadata: dict[str, object] | None = None,
    ) -> Path:
        self.config.nginx_available_dir.mkdir(parents=True, exist_ok=True)
        self.config.nginx_enabled_dir.mkdir(parents=True, exist_ok=True)
        self.config.log_dir.mkdir(parents=True, exist_ok=True)

        target = self.config_path(domain)
        if target.exists():
            if not force:
                raise SiteAlreadyExistsError(f"Nginx config already exists for {domain}")
            self.create_backup(domain, metadata=backup_metadata)

        target.write_text(content, encoding="utf-8")
        return target

    def enable_site(self, domain: str) -> Path:
        self.config.nginx_enabled_dir.mkdir(parents=True, exist_ok=True)
        enabled_path = self.enabled_path(domain)
        config_path = self.config_path(domain)
        if enabled_path.is_symlink() or enabled_path.exists():
            enabled_path.unlink()
        enabled_path.symlink_to(config_path)
        return enabled_path

    def disable_site(self, domain: str) -> None:
        enabled_path = self.enabled_path(domain)
        if enabled_path.is_symlink() or enabled_path.exists():
            enabled_path.unlink()

    def remove_config(self, domain: str) -> None:
        config_path = self.config_path(domain)
        if config_path.exists():
            config_path.unlink()

    def snapshot_site(self, domain: str) -> NginxSiteSnapshot:
        config_path = self.config_path(domain)
        enabled_path = self.enabled_path(domain)
        enabled_exists = enabled_path.exists() or enabled_path.is_symlink()
        enabled_target: str | None = None
        if enabled_path.is_symlink():
            enabled_target = str(enabled_path.readlink())
        return NginxSiteSnapshot(
            domain=domain,
            config_exists=config_path.exists(),
            config_content=config_path.read_text(encoding="utf-8") if config_path.exists() else None,
            enabled_exists=enabled_exists,
            enabled_target=enabled_target,
        )

    def restore_snapshot(self, snapshot: NginxSiteSnapshot) -> None:
        config_path = self.config_path(snapshot.domain)
        enabled_path = self.enabled_path(snapshot.domain)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        enabled_path.parent.mkdir(parents=True, exist_ok=True)

        if snapshot.config_exists and snapshot.config_content is not None:
            config_path.write_text(snapshot.config_content, encoding="utf-8")
        elif config_path.exists():
            config_path.unlink()

        if enabled_path.is_symlink() or enabled_path.exists():
            enabled_path.unlink()

        if snapshot.enabled_exists and snapshot.enabled_target:
            enabled_path.symlink_to(Path(snapshot.enabled_target))

    def validate_nginx_config(self) -> None:
        try:
            self.system_service.run(["nginx", "-t"])
        except CommandExecutionError as exc:
            raise NginxConfigError(str(exc)) from exc

    def reload_nginx(self, *, validate_first: bool = True) -> None:
        if validate_first:
            self.validate_nginx_config()
        try:
            self.system_service.run(["systemctl", "reload", "nginx"])
            return
        except CommandExecutionError:
            pass

        try:
            self.system_service.run(["nginx", "-s", "reload"])
        except CommandExecutionError as exc:
            raise NginxConfigError(str(exc)) from exc

    def list_available_domains(self) -> list[str]:
        if not self.config.nginx_available_dir.exists():
            return []
        domains: list[str] = []
        for path in self.config.nginx_available_dir.iterdir():
            if not path.is_file():
                continue
            if ".bak." in path.name:
                continue
            domains.append(path.name)
        return sorted(domains)

    def list_backups(self, domain: str) -> list[BackupEntry]:
        if not self.config.nginx_available_dir.exists():
            return []
        entries: list[BackupEntry] = []
        for path in sorted(self.config.nginx_available_dir.glob(f"{domain}.bak.*"), reverse=True):
            if path.name.endswith(".meta.json") or not path.is_file():
                continue
            metadata_path = path.with_name(f"{path.name}.meta.json")
            entries.append(
                BackupEntry(
                    name=path.name,
                    path=str(path),
                    metadata_path=str(metadata_path) if metadata_path.exists() else None,
                    has_metadata=metadata_path.exists(),
                )
            )
        return entries
