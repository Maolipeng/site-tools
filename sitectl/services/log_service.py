from __future__ import annotations

from pathlib import Path

from sitectl.exceptions import CommandExecutionError, SiteNotFoundError, ValidationError
from sitectl.models import LogResult
from sitectl.services.systemd_service import SystemdService
from sitectl.services.system_service import SystemService


class LogService:
    def __init__(self, system_service: SystemService, systemd_service: SystemdService | None = None) -> None:
        self.system_service = system_service
        self.systemd_service = systemd_service

    def _tail_lines(self, path: Path, lines: int) -> str:
        if not path.exists():
            raise SiteNotFoundError(f"Log file not found: {path}")
        content = path.read_text(encoding="utf-8")
        chunks = content.splitlines()
        selected = chunks[-lines:] if lines > 0 else chunks
        return "\n".join(selected)

    def read_nginx_access_log(self, path: Path, lines: int) -> LogResult:
        return LogResult(source=str(path), content=self._tail_lines(path, lines))

    def read_nginx_error_log(self, path: Path, lines: int) -> LogResult:
        return LogResult(source=str(path), content=self._tail_lines(path, lines))

    def read_pm2_log(self, pm2_name: str, lines: int) -> LogResult:
        completed = self.system_service.run(
            ["pm2", "logs", pm2_name, "--nostream", "--lines", str(lines)],
            check=False,
        )
        if completed.returncode != 0:
            raise SiteNotFoundError(f"Unable to read PM2 logs for {pm2_name}: {completed.stderr.strip() or completed.stdout.strip()}")
        return LogResult(source=f"pm2:{pm2_name}", content=(completed.stdout or "").rstrip())

    def read_systemd_log(self, service_name: str, lines: int) -> LogResult:
        try:
            content = self.systemd_service.read_logs(service_name, lines)
        except CommandExecutionError as exc:
            raise SiteNotFoundError(f"Unable to read systemd logs for {service_name}: {exc}") from exc
        return LogResult(source=f"systemd:{service_name}", content=content)

    def resolve_log_kind(self, access: bool, error: bool, pm2: bool, systemd: bool) -> str:
        chosen = [
            name
            for name, enabled in (("access", access), ("error", error), ("pm2", pm2), ("systemd", systemd))
            if enabled
        ]
        if len(chosen) > 1:
            raise ValidationError("Choose only one of --access, --error, --pm2, or --systemd.")
        if not chosen:
            return "error"
        return chosen[0]
