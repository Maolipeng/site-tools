from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class SiteType(str, Enum):
    NODE = "node"
    PROXY = "proxy"
    STATIC = "static"
    SYSTEMD = "systemd"


class SslMode(str, Enum):
    LETSENCRYPT = "letsencrypt"
    MANUAL = "manual"


@dataclass(slots=True)
class SiteRecord:
    domain: str
    type: SiteType
    ssl_mode: SslMode = SslMode.LETSENCRYPT
    listen_ipv6: bool = False
    upstream_host: str | None = None
    aliases: list[str] | None = None
    root: str | None = None
    port: int | None = None
    pm2_name: str | None = None
    service_name: str | None = None
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    email: str | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.aliases is None:
            self.aliases = []
        if self.type in {SiteType.NODE, SiteType.PROXY, SiteType.SYSTEMD} and not self.upstream_host:
            self.upstream_host = "127.0.0.1"

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["type"] = self.type.value
        payload["ssl_mode"] = self.ssl_mode.value
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "SiteRecord":
        return cls(
            domain=str(payload["domain"]),
            type=SiteType(str(payload["type"])),
            ssl_mode=SslMode(str(payload.get("ssl_mode", SslMode.LETSENCRYPT.value))),
            listen_ipv6=bool(payload.get("listen_ipv6", False)),
            upstream_host=str(payload["upstream_host"]) if payload.get("upstream_host") is not None else None,
            aliases=[str(item) for item in payload.get("aliases", []) if item is not None],
            root=str(payload["root"]) if payload.get("root") is not None else None,
            port=int(payload["port"]) if payload.get("port") is not None else None,
            pm2_name=str(payload["pm2_name"]) if payload.get("pm2_name") is not None else None,
            service_name=str(payload["service_name"]) if payload.get("service_name") is not None else None,
            ssl_cert_path=str(payload["ssl_cert_path"]) if payload.get("ssl_cert_path") is not None else None,
            ssl_key_path=str(payload["ssl_key_path"]) if payload.get("ssl_key_path") is not None else None,
            email=str(payload["email"]) if payload.get("email") is not None else None,
            created_at=str(payload.get("created_at") or ""),
        )


@dataclass(slots=True)
class SiteStatus:
    domain: str
    type: str
    ssl_mode: str
    listen_ipv6: bool
    upstream_host: str | None
    config_exists: bool
    enabled_exists: bool
    cert_exists: bool
    pm2_exists: bool | None
    systemd_active: bool | None
    port_open: bool


@dataclass(slots=True)
class SiteListing:
    domain: str
    type: str


@dataclass(slots=True)
class OperationPreview:
    title: str
    actions: list[str]
    config_path: str | None = None
    config_content: str | None = None


@dataclass(slots=True)
class NginxSiteSnapshot:
    domain: str
    config_exists: bool
    config_content: str | None
    enabled_exists: bool
    enabled_target: str | None


@dataclass(slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


@dataclass(slots=True)
class DoctorAdvice:
    level: str
    title: str
    detail: str
    commands: list[str]


@dataclass(slots=True)
class DoctorReport:
    checks: list[DoctorCheck]
    advice: list[DoctorAdvice] | None = None


@dataclass(slots=True)
class LogResult:
    source: str
    content: str


@dataclass(slots=True)
class HealthcheckProbe:
    name: str
    ok: bool
    detail: str
    status_code: int | None = None


@dataclass(slots=True)
class HealthcheckReport:
    domain: str
    type: str
    local_host: str | None
    probes: list[HealthcheckProbe]


@dataclass(slots=True)
class BackupEntry:
    name: str
    path: str
    metadata_path: str | None
    has_metadata: bool


@dataclass(slots=True)
class CertificateInfo:
    domain: str
    ssl_mode: str
    cert_path: str
    key_path: str | None
    exists: bool
    subject: str | None
    issuer: str | None
    not_before: str | None
    not_after: str | None
    days_remaining: int | None


@dataclass(slots=True)
class CertificateSummary:
    domain: str
    ssl_mode: str
    cert_path: str
    exists: bool
    days_remaining: int | None


@dataclass(slots=True)
class CertificateVerification:
    domain: str
    ssl_mode: str
    cert_path: str
    key_path: str | None
    cert_exists: bool
    key_exists: bool
    matches: bool
    detail: str
