from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sitectl import constants


@dataclass(frozen=True)
class NginxLayout:
    available_dir: Path
    enabled_dir: Path
    snippets_dir: Path
    main_config: Path
    log_dir: Path


NGINX_LAYOUT_CANDIDATES: tuple[NginxLayout, ...] = (
    NginxLayout(
        available_dir=Path("/etc/nginx/sites-available"),
        enabled_dir=Path("/etc/nginx/sites-enabled"),
        snippets_dir=Path("/etc/nginx/snippets"),
        main_config=Path("/etc/nginx/nginx.conf"),
        log_dir=Path("/var/log/nginx"),
    ),
    NginxLayout(
        available_dir=Path("/opt/homebrew/etc/nginx/sites-available"),
        enabled_dir=Path("/opt/homebrew/etc/nginx/sites-enabled"),
        snippets_dir=Path("/opt/homebrew/etc/nginx/snippets"),
        main_config=Path("/opt/homebrew/etc/nginx/nginx.conf"),
        log_dir=Path("/opt/homebrew/var/log/nginx"),
    ),
    NginxLayout(
        available_dir=Path("/usr/local/etc/nginx/sites-available"),
        enabled_dir=Path("/usr/local/etc/nginx/sites-enabled"),
        snippets_dir=Path("/usr/local/etc/nginx/snippets"),
        main_config=Path("/usr/local/etc/nginx/nginx.conf"),
        log_dir=Path("/usr/local/var/log/nginx"),
    ),
)


def resolve_nginx_layout() -> NginxLayout:
    for layout in NGINX_LAYOUT_CANDIDATES:
        if layout.main_config.exists():
            return layout
    return NGINX_LAYOUT_CANDIDATES[0]


def resolve_state_file() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "sitectl" / "sites.json"
    return Path(constants.DEFAULT_STATE_FILE)


@dataclass(frozen=True)
class SiteCtlConfig:
    nginx_available_dir: Path = field(default_factory=lambda: Path(constants.DEFAULT_NGINX_AVAILABLE_DIR))
    nginx_enabled_dir: Path = field(default_factory=lambda: Path(constants.DEFAULT_NGINX_ENABLED_DIR))
    nginx_snippets_dir: Path = field(default_factory=lambda: Path(constants.DEFAULT_NGINX_SNIPPETS_DIR))
    nginx_main_config: Path = field(default_factory=lambda: Path(constants.DEFAULT_NGINX_MAIN_CONFIG))
    cert_live_dir: Path = field(default_factory=lambda: Path(constants.DEFAULT_CERT_LIVE_DIR))
    state_file: Path = field(default_factory=lambda: Path(constants.DEFAULT_STATE_FILE))
    log_dir: Path = field(default_factory=lambda: Path(constants.DEFAULT_LOG_DIR))
    templates_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent / "templates")

    @classmethod
    def from_env(cls) -> "SiteCtlConfig":
        layout = resolve_nginx_layout()
        nginx_main_config = Path(os.getenv("SITECTL_NGINX_MAIN_CONFIG", str(layout.main_config)))
        nginx_root = nginx_main_config.parent
        return cls(
            nginx_available_dir=Path(os.getenv("SITECTL_NGINX_AVAILABLE_DIR", str(nginx_root / "sites-available"))),
            nginx_enabled_dir=Path(os.getenv("SITECTL_NGINX_ENABLED_DIR", str(nginx_root / "sites-enabled"))),
            nginx_snippets_dir=Path(os.getenv("SITECTL_NGINX_SNIPPETS_DIR", str(nginx_root / "snippets"))),
            nginx_main_config=nginx_main_config,
            cert_live_dir=Path(os.getenv("SITECTL_CERT_LIVE_DIR", constants.DEFAULT_CERT_LIVE_DIR)),
            state_file=Path(os.getenv("SITECTL_STATE_FILE", str(resolve_state_file()))),
            log_dir=Path(os.getenv("SITECTL_LOG_DIR", str(layout.log_dir))),
            templates_dir=Path(__file__).resolve().parent / "templates",
        )
