from __future__ import annotations

import ssl
from datetime import datetime, timezone
from pathlib import Path

from sitectl.config import SiteCtlConfig
from sitectl.exceptions import CommandExecutionError, SiteCtlError, SiteNotFoundError
from sitectl.models import CertificateInfo, CertificateSummary, CertificateVerification, SiteRecord, SslMode
from sitectl.services.system_service import SystemService


class CertificateService:
    def __init__(self, config: SiteCtlConfig, system_service: SystemService | None = None) -> None:
        self.config = config
        self.system_service = system_service or SystemService()

    def _resolve_paths(self, record: SiteRecord) -> tuple[Path, Path | None]:
        if record.ssl_mode is SslMode.MANUAL:
            cert_path = Path(record.ssl_cert_path or "")
            key_path = Path(record.ssl_key_path or "") if record.ssl_key_path else None
            return cert_path, key_path
        live_dir = self.config.cert_live_dir / record.domain
        return live_dir / "fullchain.pem", live_dir / "privkey.pem"

    def _format_name(self, entries: tuple[tuple[str, str], ...] | tuple[tuple[tuple[str, str], ...], ...] | object) -> str | None:
        if not isinstance(entries, tuple):
            return None
        flattened: list[str] = []
        for item in entries:
            if isinstance(item, tuple) and len(item) == 1 and isinstance(item[0], tuple):
                key, value = item[0]
                flattened.append(f"{key}={value}")
            elif isinstance(item, tuple) and len(item) == 2:
                key, value = item
                flattened.append(f"{key}={value}")
        return ", ".join(flattened) if flattened else None

    def _decode_certificate(self, cert_path: Path) -> dict[str, object]:
        try:
            return ssl._ssl._test_decode_cert(str(cert_path))
        except FileNotFoundError as exc:
            raise SiteNotFoundError(f"Certificate file not found: {cert_path}") from exc
        except ssl.SSLError as exc:
            raise SiteCtlError(f"Failed to decode certificate {cert_path}: {exc}") from exc

    def inspect_certificate(self, record: SiteRecord) -> CertificateInfo:
        cert_path, key_path = self._resolve_paths(record)
        cert_exists = cert_path.is_file()
        key_exists = True if key_path is None else key_path.is_file()
        if not cert_exists or not key_exists:
            return CertificateInfo(
                domain=record.domain,
                ssl_mode=record.ssl_mode.value,
                cert_path=str(cert_path),
                key_path=str(key_path) if key_path else None,
                exists=False,
                subject=None,
                issuer=None,
                not_before=None,
                not_after=None,
                days_remaining=None,
            )

        decoded = self._decode_certificate(cert_path)
        not_before_raw = str(decoded.get("notBefore")) if decoded.get("notBefore") else None
        not_after_raw = str(decoded.get("notAfter")) if decoded.get("notAfter") else None
        not_after_dt = datetime.strptime(not_after_raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc) if not_after_raw else None
        now = datetime.now(timezone.utc)
        days_remaining = (not_after_dt - now).days if not_after_dt else None
        return CertificateInfo(
            domain=record.domain,
            ssl_mode=record.ssl_mode.value,
            cert_path=str(cert_path),
            key_path=str(key_path) if key_path else None,
            exists=True,
            subject=self._format_name(decoded.get("subject")),
            issuer=self._format_name(decoded.get("issuer")),
            not_before=not_before_raw,
            not_after=not_after_raw,
            days_remaining=days_remaining,
        )

    def _read_certificate_public_key(self, cert_path: Path) -> str:
        try:
            return self.system_service.run(
                ["openssl", "x509", "-in", str(cert_path), "-pubkey", "-noout"]
            ).stdout.strip()
        except CommandExecutionError as exc:
            raise SiteCtlError(f"Failed to read certificate public key from {cert_path}:\n{exc}") from exc

    def _read_private_key_public_key(self, key_path: Path) -> str:
        try:
            return self.system_service.run(
                ["openssl", "pkey", "-in", str(key_path), "-pubout"]
            ).stdout.strip()
        except CommandExecutionError as exc:
            raise SiteCtlError(f"Failed to read private key public key from {key_path}:\n{exc}") from exc

    def verify_certificate_pair(self, record: SiteRecord) -> CertificateVerification:
        cert_path, key_path = self._resolve_paths(record)
        cert_exists = cert_path.is_file()
        key_exists = True if key_path is None else key_path.is_file()
        if not cert_exists or key_path is None or not key_exists:
            return CertificateVerification(
                domain=record.domain,
                ssl_mode=record.ssl_mode.value,
                cert_path=str(cert_path),
                key_path=str(key_path) if key_path else None,
                cert_exists=cert_exists,
                key_exists=key_exists,
                matches=False,
                detail="certificate or private key file is missing",
            )

        if not self.system_service.command_exists("openssl"):
            raise SiteCtlError("openssl is required for certificate verification.")

        cert_pubkey = self._read_certificate_public_key(cert_path)
        key_pubkey = self._read_private_key_public_key(key_path)
        matches = bool(cert_pubkey) and cert_pubkey == key_pubkey
        return CertificateVerification(
            domain=record.domain,
            ssl_mode=record.ssl_mode.value,
            cert_path=str(cert_path),
            key_path=str(key_path),
            cert_exists=True,
            key_exists=True,
            matches=matches,
            detail="certificate and private key match" if matches else "certificate and private key do not match",
        )

    def find_expiring(self, records: list[SiteRecord], days: int) -> list[CertificateSummary]:
        results: list[CertificateSummary] = []
        for record in records:
            info = self.inspect_certificate(record)
            if not info.exists or (info.days_remaining is not None and info.days_remaining <= days):
                results.append(
                    CertificateSummary(
                        domain=record.domain,
                        ssl_mode=record.ssl_mode.value,
                        cert_path=info.cert_path,
                        exists=info.exists,
                        days_remaining=info.days_remaining,
                    )
                )
        return sorted(results, key=lambda item: (item.days_remaining is None, item.days_remaining if item.days_remaining is not None else 10**9, item.domain))
