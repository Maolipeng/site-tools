from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sitectl.config import SiteCtlConfig
from sitectl.models import SiteRecord, SiteType, SslMode
from sitectl.services.nginx_service import NginxService
from sitectl.services.system_service import SystemService


class TemplateRenderingTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.config = SiteCtlConfig(
            nginx_available_dir=temp_path / "sites-available",
            nginx_enabled_dir=temp_path / "sites-enabled",
            nginx_snippets_dir=temp_path / "snippets",
            cert_live_dir=temp_path / "certs",
            state_file=temp_path / "sites.json",
            log_dir=temp_path / "logs",
            templates_dir=Path(__file__).resolve().parents[1] / "sitectl" / "templates",
        )
        self.service = NginxService(self.config, SystemService())

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_node_template_contains_required_proxy_fields(self) -> None:
        record = SiteRecord(domain="app.example.com", type=SiteType.NODE, port=3000)
        rendered = self.service.render_config(record)
        self.assertIn("listen 80;", rendered)
        self.assertIn("server_name app.example.com;", rendered)
        self.assertIn("proxy_pass http://127.0.0.1:3000;", rendered)
        self.assertIn('proxy_set_header Connection "upgrade";', rendered)
        self.assertIn("proxy_set_header Upgrade $http_upgrade;", rendered)

    def test_proxy_template_contains_server_name_and_port(self) -> None:
        record = SiteRecord(domain="api.example.com", type=SiteType.PROXY, aliases=["www.example.com"], port=8080)
        rendered = self.service.render_config(record)
        self.assertIn("listen 80;", rendered)
        self.assertIn("server_name api.example.com www.example.com;", rendered)
        self.assertIn("proxy_pass http://127.0.0.1:8080;", rendered)

    def test_static_template_contains_spa_try_files(self) -> None:
        record = SiteRecord(domain="www.example.com", type=SiteType.STATIC, root="/srv/www/example")
        rendered = self.service.render_config(record)
        self.assertIn("root /srv/www/example;", rendered)
        self.assertIn("index index.html;", rendered)
        self.assertIn("try_files $uri $uri/ /index.html;", rendered)

    def test_manual_ssl_template_contains_certificate_paths(self) -> None:
        record = SiteRecord(
            domain="secure.example.com",
            type=SiteType.PROXY,
            ssl_mode=SslMode.MANUAL,
            aliases=["cdn.example.com"],
            port=8443,
            ssl_cert_path="/etc/ssl/certs/origin.pem",
            ssl_key_path="/etc/ssl/private/origin.key",
        )
        rendered = self.service.render_config(record)
        self.assertIn("listen 443 ssl;", rendered)
        self.assertIn("server_name secure.example.com cdn.example.com;", rendered)
        self.assertIn("ssl_certificate /etc/ssl/certs/origin.pem;", rendered)
        self.assertIn("ssl_certificate_key /etc/ssl/private/origin.key;", rendered)
        self.assertIn("return 301 https://$host$request_uri;", rendered)


if __name__ == "__main__":
    unittest.main()
