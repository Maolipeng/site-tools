from __future__ import annotations

from sitectl.config import SiteCtlConfig
from sitectl.models import SiteRecord, SiteStatus, SslMode
from sitectl.services.nginx_service import NginxService
from sitectl.services.pm2_service import PM2Service
from sitectl.services.systemd_service import SystemdService
from sitectl.utils import is_port_open


class StatusService:
    def __init__(
        self,
        config: SiteCtlConfig,
        nginx_service: NginxService,
        pm2_service: PM2Service,
        systemd_service: SystemdService | None = None,
    ) -> None:
        self.config = config
        self.nginx_service = nginx_service
        self.pm2_service = pm2_service
        self.systemd_service = systemd_service

    def get_status(self, domain: str, record: SiteRecord | None = None) -> SiteStatus:
        pm2_exists: bool | None = None
        systemd_active: bool | None = None
        port_open = False
        site_type = record.type.value if record else "unknown"
        ssl_mode = record.ssl_mode.value if record else SslMode.LETSENCRYPT.value

        if record and record.type.value == "node" and record.pm2_name:
            pm2_exists = self.pm2_service.pm2_process_exists(record.pm2_name)
        if record and record.type.value == "systemd" and record.service_name:
            systemd_active = self.systemd_service.is_active(record.service_name)
        if record and record.port:
            port_open = is_port_open("127.0.0.1", record.port)

        if record and record.ssl_mode is SslMode.MANUAL:
            cert_exists = bool(record.ssl_cert_path and record.ssl_key_path) and self._manual_cert_exists(record)
        else:
            cert_exists = (self.config.cert_live_dir / domain / "fullchain.pem").exists()
        config_exists = self.nginx_service.config_path(domain).exists()
        enabled_path = self.nginx_service.enabled_path(domain)
        enabled_exists = enabled_path.exists() or enabled_path.is_symlink()
        return SiteStatus(
            domain=domain,
            type=site_type,
            ssl_mode=ssl_mode,
            config_exists=config_exists,
            enabled_exists=enabled_exists,
            cert_exists=cert_exists,
            pm2_exists=pm2_exists,
            systemd_active=systemd_active,
            port_open=port_open,
        )

    def _manual_cert_exists(self, record: SiteRecord) -> bool:
        from pathlib import Path

        return Path(record.ssl_cert_path or "").is_file() and Path(record.ssl_key_path or "").is_file()
