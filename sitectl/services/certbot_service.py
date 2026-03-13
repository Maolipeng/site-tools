from __future__ import annotations

from sitectl.exceptions import CertbotError, CommandExecutionError
from sitectl.services.system_service import SystemService


class CertbotService:
    def __init__(self, system_service: SystemService) -> None:
        self.system_service = system_service

    def request_certificate(self, domains: str | list[str], email: str) -> None:
        requested_domains = [domains] if isinstance(domains, str) else domains
        command = ["certbot", "--nginx"]
        for domain in requested_domains:
            command.extend(["-d", domain])
        command.extend(
            [
                "--non-interactive",
                "--agree-tos",
                "-m",
                email,
                "--redirect",
            ]
        )
        try:
            self.system_service.run(command)
        except CommandExecutionError as exc:
            raise CertbotError(f"Certbot failed for {', '.join(requested_domains)}:\n{exc}") from exc

    def renew(self, domain: str | None = None) -> None:
        command = ["certbot", "renew"]
        if domain:
            command.extend(["--cert-name", domain])
        try:
            self.system_service.run(command)
        except CommandExecutionError as exc:
            target = domain or "all certificates"
            raise CertbotError(f"Certbot renew failed for {target}:\n{exc}") from exc
