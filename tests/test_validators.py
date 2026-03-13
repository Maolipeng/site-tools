from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sitectl.exceptions import ValidationError
from sitectl.validators import validate_create_options, validate_domain, validate_email, validate_port, validate_upstream_host


class ValidatorsTestCase(unittest.TestCase):
    def test_validate_domain_accepts_valid_domain(self) -> None:
        self.assertEqual(validate_domain("Example.COM"), "example.com")

    def test_validate_domain_rejects_invalid_domain(self) -> None:
        with self.assertRaises(ValidationError):
            validate_domain("not_a_domain")

    def test_validate_email_accepts_valid_email(self) -> None:
        self.assertEqual(validate_email("ops@example.com"), "ops@example.com")

    def test_validate_email_rejects_invalid_email(self) -> None:
        with self.assertRaises(ValidationError):
            validate_email("invalid-email")

    def test_validate_port_accepts_valid_range(self) -> None:
        self.assertEqual(validate_port(443), 443)

    def test_validate_port_rejects_invalid_range(self) -> None:
        with self.assertRaises(ValidationError):
            validate_port(70000)

    def test_validate_upstream_host_accepts_ipv4_ipv6_and_hostname(self) -> None:
        self.assertEqual(validate_upstream_host("127.0.0.1"), "127.0.0.1")
        self.assertEqual(validate_upstream_host("::1"), "::1")
        self.assertEqual(validate_upstream_host("LOCALHOST"), "localhost")

    def test_validate_upstream_host_rejects_invalid_value(self) -> None:
        with self.assertRaises(ValidationError):
            validate_upstream_host("http://127.0.0.1")

    def test_node_requires_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValidationError):
                validate_create_options(
                    domain="app.example.com",
                    site_type="node",
                    root=temp_dir,
                    port=3000,
                    pm2_name="app",
                    service_name=None,
                    email="ops@example.com",
                    aliases=None,
                )

    def test_static_requires_existing_root(self) -> None:
        with self.assertRaises(ValidationError):
            validate_create_options(
                domain="static.example.com",
                site_type="static",
                root="/path/does/not/exist",
                port=None,
                pm2_name=None,
                service_name=None,
                email="ops@example.com",
                aliases=None,
            )

    def test_node_with_package_json_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package_json = Path(temp_dir) / "package.json"
            package_json.write_text('{"name": "demo"}', encoding="utf-8")
            site_type = validate_create_options(
                domain="app.example.com",
                site_type="node",
                root=temp_dir,
                port=3000,
                pm2_name="app",
                service_name=None,
                email="ops@example.com",
                aliases=["www.example.com"],
                upstream_host="::1",
            )
            self.assertEqual(site_type.value, "node")

    def test_static_rejects_upstream_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValidationError):
                validate_create_options(
                    domain="static.example.com",
                    site_type="static",
                    root=temp_dir,
                    port=None,
                    pm2_name=None,
                    service_name=None,
                    email="ops@example.com",
                    aliases=None,
                    upstream_host="::1",
                )

    def test_systemd_requires_service_name(self) -> None:
        with self.assertRaises(ValidationError):
            validate_create_options(
                domain="api.example.com",
                site_type="systemd",
                root=None,
                port=8080,
                pm2_name=None,
                service_name=None,
                email="ops@example.com",
                aliases=None,
            )

    def test_manual_ssl_requires_existing_cert_and_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cert_path = Path(temp_dir) / "origin.pem"
            key_path = Path(temp_dir) / "origin.key"
            cert_path.write_text("cert", encoding="utf-8")
            key_path.write_text("key", encoding="utf-8")
            site_type = validate_create_options(
                domain="secure.example.com",
                site_type="proxy",
                root=None,
                port=8443,
                pm2_name=None,
                service_name=None,
                email=None,
                aliases=None,
                ssl_mode="manual",
                ssl_cert_path=str(cert_path),
                ssl_key_path=str(key_path),
            )
            self.assertEqual(site_type.value, "proxy")

    def test_manual_ssl_rejects_missing_cert_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "origin.key"
            key_path.write_text("key", encoding="utf-8")
            with self.assertRaises(ValidationError):
                validate_create_options(
                    domain="secure.example.com",
                    site_type="proxy",
                    root=None,
                    port=8443,
                    pm2_name=None,
                    service_name=None,
                    email=None,
                    aliases=None,
                    ssl_mode="manual",
                    ssl_cert_path=str(Path(temp_dir) / "origin.pem"),
                    ssl_key_path=str(key_path),
                )

    def test_aliases_reject_duplicate_domain(self) -> None:
        with self.assertRaises(ValidationError):
            validate_create_options(
                domain="example.com",
                site_type="proxy",
                root=None,
                port=8080,
                pm2_name=None,
                service_name=None,
                email="ops@example.com",
                aliases=["example.com"],
            )


if __name__ == "__main__":
    unittest.main()
