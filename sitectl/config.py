from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from sitectl import constants


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
        return cls(
            nginx_available_dir=Path(os.getenv("SITECTL_NGINX_AVAILABLE_DIR", constants.DEFAULT_NGINX_AVAILABLE_DIR)),
            nginx_enabled_dir=Path(os.getenv("SITECTL_NGINX_ENABLED_DIR", constants.DEFAULT_NGINX_ENABLED_DIR)),
            nginx_snippets_dir=Path(os.getenv("SITECTL_NGINX_SNIPPETS_DIR", constants.DEFAULT_NGINX_SNIPPETS_DIR)),
            nginx_main_config=Path(os.getenv("SITECTL_NGINX_MAIN_CONFIG", constants.DEFAULT_NGINX_MAIN_CONFIG)),
            cert_live_dir=Path(os.getenv("SITECTL_CERT_LIVE_DIR", constants.DEFAULT_CERT_LIVE_DIR)),
            state_file=Path(os.getenv("SITECTL_STATE_FILE", constants.DEFAULT_STATE_FILE)),
            log_dir=Path(os.getenv("SITECTL_LOG_DIR", constants.DEFAULT_LOG_DIR)),
            templates_dir=Path(__file__).resolve().parent / "templates",
        )
