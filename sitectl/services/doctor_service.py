from __future__ import annotations

import os
import socket
from pathlib import Path

from sitectl.config import SiteCtlConfig
from sitectl.models import DoctorCheck, DoctorReport
from sitectl.services.system_service import SystemService


class DoctorService:
    def __init__(self, config: SiteCtlConfig, system_service: SystemService) -> None:
        self.config = config
        self.system_service = system_service

    def _check_command(self, command: str) -> DoctorCheck:
        ok = self.system_service.command_exists(command)
        detail = "found in PATH" if ok else "missing from PATH"
        return DoctorCheck(name=f"command:{command}", ok=ok, detail=detail)

    def _check_path_exists(self, name: str, path: Path) -> DoctorCheck:
        ok = path.exists()
        detail = f"exists: {path}" if ok else f"missing: {path}"
        return DoctorCheck(name=name, ok=ok, detail=detail)

    def _check_writable_parent(self, name: str, path: Path) -> DoctorCheck:
        target = path if path.is_dir() else path.parent
        current = target
        while not current.exists() and current != current.parent:
            current = current.parent
        ok = current.exists() and current.is_dir() and os.access(current, os.W_OK)
        detail = f"writable parent: {current}" if ok else f"parent is not writable or missing for {path}"
        return DoctorCheck(name=name, ok=ok, detail=detail)

    def _check_nginx_includes_sites_enabled(self) -> DoctorCheck:
        path = self.config.nginx_main_config
        if not path.exists():
            return DoctorCheck(name="nginx:include-sites-enabled", ok=False, detail=f"missing nginx config: {path}")
        content = path.read_text(encoding="utf-8")
        expected = str(self.config.nginx_enabled_dir / "*")
        ok = "sites-enabled" in content
        detail = f"contains sites-enabled include ({expected})" if ok else f"nginx config does not reference sites-enabled ({path})"
        return DoctorCheck(name="nginx:include-sites-enabled", ok=ok, detail=detail)

    def _check_port_bindable(self, port: int) -> DoctorCheck:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", port))
            except OSError as exc:
                return DoctorCheck(name=f"port:{port}", ok=False, detail=f"port is in use or requires privileges: {exc}")
        return DoctorCheck(name=f"port:{port}", ok=True, detail="port appears available for binding")

    def run(self) -> DoctorReport:
        checks = [
            self._check_command("nginx"),
            self._check_command("certbot"),
            self._check_command("pm2"),
            self._check_command("npm"),
            self._check_command("systemctl"),
            self._check_command("journalctl"),
            self._check_path_exists("path:nginx-available", self.config.nginx_available_dir),
            self._check_path_exists("path:nginx-enabled", self.config.nginx_enabled_dir),
            self._check_writable_parent("path:state-parent", self.config.state_file),
            self._check_nginx_includes_sites_enabled(),
            self._check_port_bindable(80),
            self._check_port_bindable(443),
        ]
        return DoctorReport(checks=checks)
