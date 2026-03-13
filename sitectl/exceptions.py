from __future__ import annotations


class SiteCtlError(Exception):
    """Base exception for sitectl."""


class ValidationError(SiteCtlError):
    """Raised when command input is invalid."""


class CommandExecutionError(SiteCtlError):
    def __init__(
        self,
        command: list[str],
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        message: str | None = None,
    ) -> None:
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        parts = [message or f"Command failed ({returncode}): {' '.join(command)}"]
        if stdout.strip():
            parts.append(f"stdout: {stdout.strip()}")
        if stderr.strip():
            parts.append(f"stderr: {stderr.strip()}")
        super().__init__("\n".join(parts))


class NginxConfigError(SiteCtlError):
    """Raised when Nginx configuration validation or reload fails."""


class CertbotError(SiteCtlError):
    """Raised when certbot operations fail."""


class StateError(SiteCtlError):
    """Raised when local state persistence fails."""


class SiteAlreadyExistsError(SiteCtlError):
    """Raised when a site already exists and force is not enabled."""


class SiteNotFoundError(SiteCtlError):
    """Raised when a requested site cannot be found."""

