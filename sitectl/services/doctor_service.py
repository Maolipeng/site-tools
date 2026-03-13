from __future__ import annotations

import os
import socket
import ipaddress
import re
from pathlib import Path

from sitectl.config import SiteCtlConfig
from sitectl.models import DoctorAdvice, DoctorCheck, DoctorReport
from sitectl.services.system_service import SystemService


IPV6_PATTERN = re.compile(r"\binet6\s+([0-9a-fA-F:]+)/\d+\b")


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

    def _check_port_bindable_ipv6(self, port: int) -> DoctorCheck:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("::", port))
            except OSError as exc:
                return DoctorCheck(name=f"port6:{port}", ok=False, detail=f"IPv6 port is in use, unsupported, or requires privileges: {exc}")
        return DoctorCheck(name=f"port6:{port}", ok=True, detail="IPv6 port appears available for binding")

    def _discover_global_ipv6_addresses(self) -> list[str]:
        addresses: list[str] = []
        if self.system_service.command_exists("ip"):
            completed = self.system_service.run(["ip", "-6", "addr", "show", "scope", "global"], check=False)
            for candidate in IPV6_PATTERN.findall(completed.stdout or ""):
                try:
                    address = ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                if address.version == 6 and address.is_global:
                    addresses.append(candidate)
        if addresses:
            return sorted(set(addresses))

        try:
            infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6, socket.SOCK_STREAM)
        except socket.gaierror:
            return []
        for info in infos:
            candidate = info[4][0]
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if address.version == 6 and address.is_global:
                addresses.append(candidate)
        return sorted(set(addresses))

    def _check_global_ipv6(self) -> DoctorCheck:
        addresses = self._discover_global_ipv6_addresses()
        if not addresses:
            return DoctorCheck(name="network:global-ipv6", ok=False, detail="no global IPv6 address detected on this host")
        return DoctorCheck(
            name="network:global-ipv6",
            ok=True,
            detail=f"detected global IPv6 address(es): {', '.join(addresses)}",
        )

    def _resolve_domain_aaaa(self, domain: str) -> list[str]:
        try:
            infos = socket.getaddrinfo(domain, None, socket.AF_INET6, socket.SOCK_STREAM)
        except socket.gaierror:
            return []
        addresses: list[str] = []
        for info in infos:
            candidate = info[4][0]
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if address.version == 6:
                addresses.append(candidate)
        return sorted(set(addresses))

    def _check_domain_ipv6_dns(self, domain: str, local_ipv6_addresses: list[str]) -> DoctorCheck:
        resolved = self._resolve_domain_aaaa(domain)
        if not resolved:
            return DoctorCheck(name=f"dns:aaaa:{domain}", ok=False, detail=f"no AAAA record resolved for {domain}")
        if local_ipv6_addresses and any(address in local_ipv6_addresses for address in resolved):
            return DoctorCheck(
                name=f"dns:aaaa:{domain}",
                ok=True,
                detail=f"AAAA for {domain} resolves to this host: {', '.join(resolved)}",
            )
        if local_ipv6_addresses:
            return DoctorCheck(
                name=f"dns:aaaa:{domain}",
                ok=False,
                detail=(
                    f"AAAA for {domain} resolves to {', '.join(resolved)}, which does not match local IPv6 "
                    f"{', '.join(local_ipv6_addresses)}"
                ),
            )
        return DoctorCheck(name=f"dns:aaaa:{domain}", ok=True, detail=f"AAAA for {domain} resolves to {', '.join(resolved)}")

    def _build_advice(
        self,
        checks: list[DoctorCheck],
        *,
        domain: str | None,
        site_type: str | None,
        port: int | None,
        upstream_host: str | None,
        listen_ipv6: bool,
        email: str | None,
        ssl_mode: str,
    ) -> list[DoctorAdvice]:
        check_map = {check.name: check for check in checks}
        advice: list[DoctorAdvice] = []
        ipv6_check = check_map.get("network:global-ipv6")
        local_ipv6_addresses: list[str] = []
        if ipv6_check and ipv6_check.ok:
            local_ipv6_addresses = [item.strip() for item in ipv6_check.detail.split(": ", 1)[-1].split(",") if item.strip()]
        if ipv6_check and ipv6_check.ok:
            addresses = ipv6_check.detail.split(": ", 1)[-1]
            commands = [
                "sitectl create --domain example.com --type proxy --port 8080 --upstream-host ::1 --listen-ipv6 --email ops@example.com",
                "sitectl create --domain example.com --type static --root /srv/www/example --listen-ipv6 --email ops@example.com",
            ]
            advice.append(
                DoctorAdvice(
                    level="info",
                    title="Public IPv6 detected",
                    detail=(
                        f"This host has public IPv6 connectivity ({addresses}). You can point an AAAA record at one of these addresses, "
                        "enable explicit IPv6 listen directives, and then use Let's Encrypt or a manual certificate for HTTPS."
                    ),
                    commands=commands,
                )
            )
        if domain and local_ipv6_addresses:
            dns_check = check_map.get(f"dns:aaaa:{domain}")
            if dns_check and not dns_check.ok:
                first_ipv6 = local_ipv6_addresses[0]
                detail = (
                    f"Set an AAAA record for {domain} to {first_ipv6} before enabling public IPv6 traffic or requesting HTTPS certificates."
                )
                if ssl_mode == "letsencrypt":
                    detail += " Let's Encrypt validation over IPv6 is more reliable once DNS already points at this host."
                suggested_type = site_type or "proxy"
                suggested_port = port or 8080
                suggested_upstream = upstream_host or "::1"
                command = (
                    f"sitectl create --domain {domain} --type {suggested_type} --port {suggested_port} "
                    f"--upstream-host {suggested_upstream} {'--listen-ipv6 ' if listen_ipv6 else ''}"
                    f"{f'--email {email} ' if email else ''}".strip()
                )
                advice.append(
                    DoctorAdvice(
                        level="warning",
                        title="AAAA record still needs setup",
                        detail=detail,
                        commands=[command],
                    )
                )
            elif dns_check and dns_check.ok and ssl_mode == "letsencrypt":
                suggested_type = site_type or "proxy"
                suggested_port = port or 8080
                suggested_upstream = upstream_host or "::1"
                command = (
                    f"sitectl create --domain {domain} --type {suggested_type} --port {suggested_port} "
                    f"--upstream-host {suggested_upstream} {'--listen-ipv6 ' if listen_ipv6 else ''}"
                    f"{f'--email {email} ' if email else ''}".strip()
                )
                advice.append(
                    DoctorAdvice(
                        level="info",
                        title="IPv6 DNS looks ready for HTTPS",
                        detail=f"{domain} already has an AAAA record that points at this host. You can proceed with IPv6-enabled site creation and HTTPS.",
                        commands=[command],
                    )
                )
        return advice

    def run(
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
        checks = [
            self._check_command("nginx"),
            self._check_command("certbot"),
            self._check_command("pm2"),
            self._check_command("npm"),
            self._check_command("systemctl"),
            self._check_command("journalctl"),
            self._check_command("ip"),
            self._check_path_exists("path:nginx-available", self.config.nginx_available_dir),
            self._check_path_exists("path:nginx-enabled", self.config.nginx_enabled_dir),
            self._check_writable_parent("path:state-parent", self.config.state_file),
            self._check_nginx_includes_sites_enabled(),
            self._check_global_ipv6(),
            self._check_port_bindable(80),
            self._check_port_bindable(443),
            self._check_port_bindable_ipv6(80),
            self._check_port_bindable_ipv6(443),
        ]
        if domain:
            ipv6_check = next((check for check in checks if check.name == "network:global-ipv6"), None)
            local_ipv6_addresses: list[str] = []
            if ipv6_check and ipv6_check.ok:
                local_ipv6_addresses = [item.strip() for item in ipv6_check.detail.split(": ", 1)[-1].split(",") if item.strip()]
            checks.append(self._check_domain_ipv6_dns(domain, local_ipv6_addresses))
        return DoctorReport(
            checks=checks,
            advice=self._build_advice(
                checks,
                domain=domain,
                site_type=site_type,
                port=port,
                upstream_host=upstream_host,
                listen_ipv6=listen_ipv6,
                email=email,
                ssl_mode=ssl_mode,
            ),
        )
