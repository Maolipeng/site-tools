from __future__ import annotations

from sitectl.exceptions import CommandExecutionError
from sitectl.services.system_service import SystemService


class SystemdService:
    def __init__(self, system_service: SystemService) -> None:
        self.system_service = system_service

    def restart_service(self, service_name: str) -> None:
        self.system_service.run(["systemctl", "restart", service_name])

    def stop_service(self, service_name: str) -> None:
        self.system_service.run(["systemctl", "stop", service_name])

    def is_active(self, service_name: str) -> bool:
        completed = self.system_service.run(["systemctl", "is-active", service_name], check=False)
        return completed.returncode == 0 and (completed.stdout or "").strip() == "active"

    def read_logs(self, service_name: str, lines: int) -> str:
        completed = self.system_service.run(
            ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
            check=False,
        )
        if completed.returncode != 0:
            raise CommandExecutionError(
                ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
                completed.returncode,
                completed.stdout,
                completed.stderr,
            )
        return (completed.stdout or "").rstrip()
