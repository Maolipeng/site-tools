from __future__ import annotations

import re
from pathlib import Path

from sitectl.exceptions import ValidationError
from sitectl.models import SslMode, SiteType


DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?!-)(?:[a-zA-Z0-9-]{1,63}\.)+[A-Za-z]{2,63}$"
)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_domain(domain: str) -> str:
    if not DOMAIN_PATTERN.match(domain):
        raise ValidationError(f"Invalid domain: {domain}")
    return domain.lower()


def validate_email(email: str) -> str:
    if not EMAIL_PATTERN.match(email):
        raise ValidationError(f"Invalid email: {email}")
    return email


def validate_port(port: int | None) -> int:
    if port is None:
        raise ValidationError("Port is required.")
    if not 1 <= port <= 65535:
        raise ValidationError(f"Invalid port: {port}")
    return port


def validate_aliases(aliases: list[str] | None, domain: str) -> list[str]:
    normalized: list[str] = []
    seen = {domain.lower()}
    for alias in aliases or []:
        validated = validate_domain(alias)
        if validated in seen:
            raise ValidationError(f"Duplicate alias detected: {validated}")
        seen.add(validated)
        normalized.append(validated)
    return normalized


def validate_ssl_mode(ssl_mode: str | None) -> SslMode:
    return SslMode(ssl_mode or SslMode.LETSENCRYPT.value)


def validate_manual_cert_paths(ssl_cert_path: str | None, ssl_key_path: str | None) -> tuple[str, str]:
    if not ssl_cert_path:
        raise ValidationError("--ssl-cert is required when --ssl-mode manual is used.")
    if not ssl_key_path:
        raise ValidationError("--ssl-key is required when --ssl-mode manual is used.")
    cert_path = Path(ssl_cert_path)
    key_path = Path(ssl_key_path)
    if not cert_path.is_file():
        raise ValidationError(f"SSL certificate file not found: {ssl_cert_path}")
    if not key_path.is_file():
        raise ValidationError(f"SSL private key file not found: {ssl_key_path}")
    return str(cert_path), str(key_path)


def validate_node_root(root: str | None) -> Path:
    if not root:
        raise ValidationError("--root is required for node sites.")
    root_path = Path(root)
    package_json = root_path / "package.json"
    if not root_path.is_dir():
        raise ValidationError(f"Node root does not exist: {root}")
    if not package_json.is_file():
        raise ValidationError(f"package.json not found in {root}")
    return root_path


def validate_static_root(root: str | None) -> Path:
    if not root:
        raise ValidationError("--root is required for static sites.")
    root_path = Path(root)
    if not root_path.is_dir():
        raise ValidationError(f"Static root does not exist: {root}")
    return root_path


def validate_create_options(
    *,
    domain: str,
    site_type: str,
    root: str | None,
    port: int | None,
    pm2_name: str | None,
    service_name: str | None,
    email: str | None,
    aliases: list[str] | None = None,
    ssl_mode: str | None = None,
    ssl_cert_path: str | None = None,
    ssl_key_path: str | None = None,
) -> SiteType:
    normalized_type = SiteType(site_type)
    normalized_domain = validate_domain(domain)
    validate_aliases(aliases, normalized_domain)
    normalized_ssl_mode = validate_ssl_mode(ssl_mode)

    if normalized_type is SiteType.NODE:
        validate_node_root(root)
        validate_port(port)
        if not pm2_name:
            raise ValidationError("--pm2-name is required for node sites.")
        if normalized_ssl_mode is SslMode.LETSENCRYPT and not email:
            raise ValidationError("--email is required for node sites.")
        if email:
            validate_email(email)
    elif normalized_type is SiteType.SYSTEMD:
        validate_port(port)
        if not service_name:
            raise ValidationError("--service-name is required for systemd sites.")
        if normalized_ssl_mode is SslMode.LETSENCRYPT and not email:
            raise ValidationError("--email is required for systemd sites.")
        if email:
            validate_email(email)
    elif normalized_type is SiteType.PROXY:
        validate_port(port)
        if normalized_ssl_mode is SslMode.LETSENCRYPT and not email:
            raise ValidationError("--email is required for proxy sites.")
        if email:
            validate_email(email)
    elif normalized_type is SiteType.STATIC:
        validate_static_root(root)
        if normalized_ssl_mode is SslMode.LETSENCRYPT and not email:
            raise ValidationError("--email is required for static sites.")
        if email:
            validate_email(email)

    if normalized_ssl_mode is SslMode.MANUAL:
        validate_manual_cert_paths(ssl_cert_path, ssl_key_path)

    return normalized_type
