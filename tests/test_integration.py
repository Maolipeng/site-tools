from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from sitectl.config import SiteCtlConfig
from sitectl.exceptions import CommandExecutionError, SiteCtlError
from sitectl.services.certbot_service import CertbotService
from sitectl.services.certificate_service import CertificateService
from sitectl.services.doctor_service import DoctorService
from sitectl.services.healthcheck_service import HealthcheckService
from sitectl.services.log_service import LogService
from sitectl.services.nginx_service import NginxService
from sitectl.services.pm2_service import PM2Service
from sitectl.services.site_service import SiteService
from sitectl.services.status_service import StatusService
from sitectl.services.systemd_service import SystemdService


class FakeSystemService:
    def __init__(self) -> None:
        self.commands: list[dict[str, object]] = []
        self.pm2_processes: set[str] = set()
        self.systemd_services: set[str] = set()
        self.fail_pm2_delete: set[str] = set()
        self.fail_commands: dict[tuple[str, ...], str] = {}
        self.global_ipv6_addresses = ["2606:4700:4700::1111"]
        self.available_commands = {"nginx", "certbot", "pm2", "npm", "systemctl", "journalctl", "openssl", "ip"}

    def command_exists(self, command: str) -> bool:
        return command in self.available_commands

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.commands.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env,
                "check": check,
                "timeout": timeout,
            }
        )

        failure_message = self.fail_commands.get(tuple(command))
        if failure_message is not None:
            if check:
                raise CommandExecutionError(command, 1, stderr=failure_message)
            return subprocess.CompletedProcess(command, 1, stdout="", stderr=failure_message)

        if command[:2] == ["pm2", "jlist"]:
            stdout = json.dumps([{"name": name} for name in sorted(self.pm2_processes)])
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        if command[:2] == ["pm2", "logs"]:
            pm2_name = command[2]
            if pm2_name not in self.pm2_processes:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="process not found")
            return subprocess.CompletedProcess(command, 0, stdout=f"{pm2_name}: line1\n{pm2_name}: line2", stderr="")

        if command[:2] == ["systemctl", "is-active"]:
            service_name = command[2]
            if service_name in self.systemd_services:
                return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")
            return subprocess.CompletedProcess(command, 3, stdout="inactive\n", stderr="")

        if command[:2] == ["systemctl", "restart"]:
            self.systemd_services.add(command[2])
            return subprocess.CompletedProcess(command, 0, stdout="restarted", stderr="")

        if command[:2] == ["systemctl", "stop"]:
            self.systemd_services.discard(command[2])
            return subprocess.CompletedProcess(command, 0, stdout="stopped", stderr="")

        if command[:2] == ["journalctl", "-u"]:
            service_name = command[2]
            if service_name not in self.systemd_services:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="unit not found")
            return subprocess.CompletedProcess(command, 0, stdout=f"{service_name}: log1\n{service_name}: log2", stderr="")

        if command == ["ip", "-6", "addr", "show", "scope", "global"]:
            stdout = "\n".join(f"    inet6 {address}/64 scope global dynamic" for address in self.global_ipv6_addresses)
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        if command[:3] == ["openssl", "x509", "-in"]:
            cert_path = Path(command[3])
            return subprocess.CompletedProcess(command, 0, stdout=f"PUBKEY:{cert_path.read_text(encoding='utf-8').strip()}", stderr="")

        if command[:3] == ["openssl", "pkey", "-in"]:
            key_path = Path(command[3])
            return subprocess.CompletedProcess(command, 0, stdout=f"PUBKEY:{key_path.read_text(encoding='utf-8').strip()}", stderr="")

        if command[:4] == ["pm2", "start", "npm", "--name"]:
            self.pm2_processes.add(command[4])
            return subprocess.CompletedProcess(command, 0, stdout="started", stderr="")

        if command[:2] == ["pm2", "restart"]:
            self.pm2_processes.add(command[2])
            return subprocess.CompletedProcess(command, 0, stdout="restarted", stderr="")

        if command[:2] == ["pm2", "delete"]:
            pm2_name = command[2]
            if pm2_name in self.fail_pm2_delete:
                if check:
                    raise CommandExecutionError(command, 1, stderr="process not found")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="process not found")
            self.pm2_processes.discard(pm2_name)
            return subprocess.CompletedProcess(command, 0, stdout="deleted", stderr="")

        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


class SiteServiceIntegrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.config = SiteCtlConfig(
            nginx_available_dir=temp_path / "sites-available",
            nginx_enabled_dir=temp_path / "sites-enabled",
            nginx_snippets_dir=temp_path / "snippets",
            nginx_main_config=temp_path / "nginx" / "nginx.conf",
            cert_live_dir=temp_path / "letsencrypt" / "live",
            state_file=temp_path / "etc" / "sitectl" / "sites.json",
            log_dir=temp_path / "logs",
            templates_dir=Path(__file__).resolve().parents[1] / "sitectl" / "templates",
        )
        self.system = FakeSystemService()
        self.nginx_service = NginxService(self.config, self.system)
        self.certbot_service = CertbotService(self.system)
        self.pm2_service = PM2Service(self.system)
        self.systemd_service = SystemdService(self.system)
        self.status_service = StatusService(self.config, self.nginx_service, self.pm2_service, self.systemd_service)
        self.log_service = LogService(self.system, self.systemd_service)
        self.doctor_service = DoctorService(self.config, self.system)
        self.healthcheck_service = HealthcheckService()
        self.certificate_service = CertificateService(self.config, self.system)
        self.site_service = SiteService(
            self.config,
            self.nginx_service,
            self.certbot_service,
            self.pm2_service,
            self.status_service,
            self.log_service,
            self.doctor_service,
            self.systemd_service,
            self.healthcheck_service,
            self.certificate_service,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_proxy_site_writes_config_state_and_invokes_services(self) -> None:
        record = self.site_service.create_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=["www.example.com"],
            force=False,
        )

        config_path = self.config.nginx_available_dir / "api.example.com"
        enabled_path = self.config.nginx_enabled_dir / "api.example.com"
        state_payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))

        self.assertEqual(record.domain, "api.example.com")
        self.assertEqual(record.aliases, ["www.example.com"])
        self.assertTrue(config_path.exists())
        self.assertTrue(enabled_path.is_symlink())
        self.assertEqual(enabled_path.resolve(), config_path.resolve())
        self.assertEqual(state_payload["sites"][0]["domain"], "api.example.com")
        self.assertEqual(state_payload["sites"][0]["type"], "proxy")
        self.assertEqual(state_payload["sites"][0]["aliases"], ["www.example.com"])
        self.assertIn("server_name api.example.com www.example.com;", config_path.read_text(encoding="utf-8"))

        commands = [entry["command"] for entry in self.system.commands]
        self.assertIn(["nginx", "-t"], commands)
        self.assertIn(["systemctl", "reload", "nginx"], commands)
        self.assertIn(
            [
                "certbot",
                "--nginx",
                "-d",
                "api.example.com",
                "-d",
                "www.example.com",
                "--non-interactive",
                "--agree-tos",
                "-m",
                "ops@example.com",
                "--redirect",
            ],
            commands,
        )

    def test_force_create_backs_up_existing_config(self) -> None:
        original_path = self.config.nginx_available_dir / "api.example.com"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_text("old config", encoding="utf-8")

        self.site_service.create_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
            force=True,
        )

        backups = [path for path in self.config.nginx_available_dir.glob("api.example.com.bak.*") if not path.name.endswith(".meta.json")]
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "old config")
        self.assertIn("proxy_pass http://127.0.0.1:8080;", original_path.read_text(encoding="utf-8"))

    def test_create_proxy_site_supports_ipv6_listen_and_upstream_host(self) -> None:
        record = self.site_service.create_site(
            domain="ipv6.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
            listen_ipv6=True,
            upstream_host="::1",
            force=False,
        )

        config_text = (self.config.nginx_available_dir / "ipv6.example.com").read_text(encoding="utf-8")
        state_payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        status = self.site_service.get_status("ipv6.example.com")

        self.assertTrue(record.listen_ipv6)
        self.assertEqual(record.upstream_host, "::1")
        self.assertIn("listen [::]:80;", config_text)
        self.assertIn("proxy_pass http://[::1]:8080;", config_text)
        self.assertTrue(state_payload["sites"][0]["listen_ipv6"])
        self.assertEqual(state_payload["sites"][0]["upstream_host"], "::1")
        self.assertTrue(status.listen_ipv6)
        self.assertEqual(status.upstream_host, "::1")

    def test_create_node_site_runs_npm_build_and_pm2_start(self) -> None:
        app_root = Path(self.temp_dir.name) / "node-app"
        app_root.mkdir(parents=True, exist_ok=True)
        (app_root / "package.json").write_text(
            json.dumps(
                {
                    "name": "node-app",
                    "scripts": {
                        "build": "next build",
                        "start": "next start",
                    },
                }
            ),
            encoding="utf-8",
        )

        self.site_service.create_site(
            domain="app.example.com",
            site_type="node",
            root=str(app_root),
            port=3000,
            pm2_name="app-example",
            service_name=None,
            email="ops@example.com",
            aliases=None,
            force=False,
        )

        commands = self.system.commands
        self.assertEqual(commands[0]["command"], ["npm", "install"])
        self.assertEqual(commands[0]["cwd"], app_root)
        self.assertEqual(commands[1]["command"], ["npm", "run", "build"])
        self.assertEqual(commands[1]["cwd"], app_root)

        pm2_start = next(entry for entry in commands if entry["command"][:4] == ["pm2", "start", "npm", "--name"])
        self.assertEqual(pm2_start["command"], ["pm2", "start", "npm", "--name", "app-example", "--", "run", "start"])
        self.assertEqual(pm2_start["cwd"], app_root)
        self.assertEqual(pm2_start["env"]["PORT"], "3000")
        self.assertIn("app-example", self.system.pm2_processes)

    def test_remove_site_deletes_files_and_updates_state(self) -> None:
        self.site_service.create_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
            force=False,
        )

        removed_domain = self.site_service.remove_site("api.example.com")
        commands = [entry["command"] for entry in self.system.commands]

        self.assertEqual(removed_domain, "api.example.com")
        self.assertFalse((self.config.nginx_available_dir / "api.example.com").exists())
        self.assertFalse((self.config.nginx_enabled_dir / "api.example.com").exists())
        state_payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state_payload["sites"], [])
        self.assertGreaterEqual(commands.count(["nginx", "-t"]), 2)
        self.assertGreaterEqual(commands.count(["systemctl", "reload", "nginx"]), 2)

    def test_update_site_rewrites_config_and_state(self) -> None:
        self.site_service.create_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
            force=False,
        )

        updated = self.site_service.update_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=9090,
            pm2_name=None,
            service_name=None,
            email="infra@example.com",
            aliases=["new.example.com"],
        )

        self.assertEqual(updated.port, 9090)
        self.assertEqual(updated.email, "infra@example.com")
        self.assertEqual(updated.aliases, ["new.example.com"])
        config_text = (self.config.nginx_available_dir / "api.example.com").read_text(encoding="utf-8")
        self.assertIn("proxy_pass http://127.0.0.1:9090;", config_text)
        self.assertIn("server_name api.example.com new.example.com;", config_text)
        state_payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state_payload["sites"][0]["port"], 9090)
        self.assertEqual(state_payload["sites"][0]["email"], "infra@example.com")
        self.assertEqual(state_payload["sites"][0]["aliases"], ["new.example.com"])
        backups = [path for path in self.config.nginx_available_dir.glob("api.example.com.bak.*") if not path.name.endswith(".meta.json")]
        self.assertEqual(len(backups), 1)

    def test_create_dry_run_does_not_write_files_or_execute_commands(self) -> None:
        result = self.site_service.create_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=["www.example.com"],
            dry_run=True,
        )

        self.assertEqual(result.title, "Create site api.example.com")
        self.assertIn("configure server aliases: www.example.com", result.actions)
        self.assertIn("run nginx -t", result.actions)
        self.assertIn("server_name api.example.com www.example.com;", result.config_content)
        self.assertIn("proxy_pass http://127.0.0.1:8080;", result.config_content)
        self.assertFalse(self.config.nginx_available_dir.exists())
        self.assertFalse(self.config.state_file.exists())
        self.assertEqual(self.system.commands, [])

    def test_create_dry_run_ipv6_letsencrypt_mentions_aaaa_readiness(self) -> None:
        result = self.site_service.create_site(
            domain="ipv6.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
            listen_ipv6=True,
            upstream_host="::1",
            dry_run=True,
        )

        self.assertIn("add explicit IPv6 listen directives for Nginx", result.actions)
        self.assertIn(
            "verify AAAA for ipv6.example.com points at this host before requesting Let's Encrypt over IPv6",
            result.actions,
        )

    def test_create_rolls_back_nginx_and_state_when_certbot_fails(self) -> None:
        original_path = self.config.nginx_available_dir / "api.example.com"
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_text("server { listen 80; }", encoding="utf-8")
        enabled_path = self.config.nginx_enabled_dir / "api.example.com"
        enabled_path.parent.mkdir(parents=True, exist_ok=True)
        enabled_path.symlink_to(original_path)
        self.config.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.state_file.write_text(
            json.dumps(
                {
                    "sites": [
                        {
                            "domain": "api.example.com",
                            "type": "proxy",
                            "root": None,
                            "port": 8080,
                            "pm2_name": None,
                            "email": "ops@example.com",
                            "created_at": "2026-03-13T12:00:00+00:00",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.system.fail_commands[
            (
                "certbot",
                "--nginx",
                "-d",
                "api.example.com",
                "--non-interactive",
                "--agree-tos",
                "-m",
                "ops@example.com",
                "--redirect",
            )
        ] = "certbot failed"

        with self.assertRaises(Exception):
            self.site_service.create_site(
                domain="api.example.com",
                site_type="proxy",
                root=None,
                port=9090,
                pm2_name=None,
                service_name=None,
                email="ops@example.com",
                aliases=None,
                force=True,
            )

        self.assertEqual(original_path.read_text(encoding="utf-8"), "server { listen 80; }")
        self.assertTrue(enabled_path.is_symlink())
        state_payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state_payload["sites"][0]["port"], 8080)

    def test_update_dry_run_describes_pm2_cleanup(self) -> None:
        app_root = Path(self.temp_dir.name) / "update-node-app"
        app_root.mkdir(parents=True, exist_ok=True)
        (app_root / "package.json").write_text(
            json.dumps({"name": "update-node-app", "scripts": {"start": "node server.js"}}),
            encoding="utf-8",
        )
        self.site_service.create_site(
            domain="app.example.com",
            site_type="node",
            root=str(app_root),
            port=3000,
            pm2_name="old-app",
            service_name=None,
            email="ops@example.com",
            aliases=None,
        )

        result = self.site_service.update_site(
            domain="app.example.com",
            site_type="proxy",
            root=None,
            port=4000,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
            dry_run=True,
        )

        self.assertIn("delete old PM2 process old-app after successful update", result.actions)

    def test_list_sites_falls_back_to_nginx_scan_when_state_missing(self) -> None:
        self.config.nginx_available_dir.mkdir(parents=True, exist_ok=True)
        (self.config.nginx_available_dir / "one.example.com").write_text("server {}", encoding="utf-8")
        (self.config.nginx_available_dir / "one.example.com.bak.20260313120000").write_text(
            "backup",
            encoding="utf-8",
        )
        (self.config.nginx_available_dir / "two.example.com").write_text("server {}", encoding="utf-8")

        listings = self.site_service.list_sites()

        self.assertEqual([item.domain for item in listings], ["one.example.com", "two.example.com"])
        self.assertTrue(all(item.type == "unknown" for item in listings))

    def test_status_reports_cert_pm2_and_open_port(self) -> None:
        app_root = Path(self.temp_dir.name) / "node-status-app"
        app_root.mkdir(parents=True, exist_ok=True)
        (app_root / "package.json").write_text(
            json.dumps({"name": "status-app", "scripts": {"start": "node server.js"}}),
            encoding="utf-8",
        )

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("127.0.0.1", 0))
        server_socket.listen(1)
        port = server_socket.getsockname()[1]

        try:
            self.site_service.create_site(
                domain="status.example.com",
                site_type="node",
                root=str(app_root),
                port=port,
                pm2_name="status-app",
                service_name=None,
                email="ops@example.com",
                aliases=None,
                force=False,
            )

            cert_dir = self.config.cert_live_dir / "status.example.com"
            cert_dir.mkdir(parents=True, exist_ok=True)
            (cert_dir / "fullchain.pem").write_text("certificate", encoding="utf-8")

            status = self.site_service.get_status("status.example.com")
        finally:
            server_socket.close()

        self.assertEqual(status.domain, "status.example.com")
        self.assertEqual(status.type, "node")
        self.assertFalse(status.listen_ipv6)
        self.assertEqual(status.upstream_host, "127.0.0.1")
        self.assertTrue(status.config_exists)
        self.assertTrue(status.enabled_exists)
        self.assertTrue(status.cert_exists)
        self.assertTrue(status.pm2_exists)
        self.assertIsNone(status.systemd_active)
        self.assertTrue(status.port_open)

    def test_renew_runs_certbot_then_nginx_validation_and_reload(self) -> None:
        result = self.site_service.renew_certificates("api.example.com")
        commands = [entry["command"] for entry in self.system.commands]

        self.assertEqual(result, "api.example.com")
        self.assertEqual(commands[0], ["certbot", "renew", "--cert-name", "api.example.com"])
        self.assertEqual(commands[1], ["nginx", "-t"])
        self.assertEqual(commands[2], ["systemctl", "reload", "nginx"])

    def test_get_logs_reads_error_log_file(self) -> None:
        log_path = self.config.log_dir / "api.example.com.error.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")

        result = self.site_service.get_logs("api.example.com", "error", lines=2)

        self.assertEqual(result.source, str(log_path))
        self.assertEqual(result.content, "two\nthree")

    def test_get_logs_reads_pm2_log_for_node_site(self) -> None:
        app_root = Path(self.temp_dir.name) / "pm2-log-app"
        app_root.mkdir(parents=True, exist_ok=True)
        (app_root / "package.json").write_text(
            json.dumps({"name": "pm2-log-app", "scripts": {"start": "node server.js"}}),
            encoding="utf-8",
        )
        self.site_service.create_site(
            domain="pm2.example.com",
            site_type="node",
            root=str(app_root),
            port=3000,
            pm2_name="pm2-log-app",
            service_name=None,
            email="ops@example.com",
            aliases=None,
        )

        result = self.site_service.get_logs("pm2.example.com", "pm2", lines=50)

        self.assertEqual(result.source, "pm2:pm2-log-app")
        self.assertIn("pm2-log-app: line1", result.content)

    def test_create_systemd_site_restarts_service_and_tracks_status(self) -> None:
        record = self.site_service.create_site(
            domain="svc.example.com",
            site_type="systemd",
            root=None,
            port=9000,
            pm2_name=None,
            service_name="svc-app",
            email="ops@example.com",
            aliases=None,
        )

        status = self.site_service.get_status("svc.example.com")
        commands = [entry["command"] for entry in self.system.commands]

        self.assertEqual(record.type.value, "systemd")
        self.assertEqual(record.service_name, "svc-app")
        self.assertIn(["systemctl", "restart", "svc-app"], commands)
        self.assertTrue(status.systemd_active)
        self.assertIsNone(status.pm2_exists)

    def test_create_manual_ssl_site_uses_existing_certificate_without_certbot(self) -> None:
        cert_path = Path(self.temp_dir.name) / "cloudflare-origin.pem"
        key_path = Path(self.temp_dir.name) / "cloudflare-origin.key"
        cert_path.write_text("cert", encoding="utf-8")
        key_path.write_text("key", encoding="utf-8")

        record = self.site_service.create_site(
            domain="secure.example.com",
            site_type="proxy",
            root=None,
            port=8443,
            pm2_name=None,
            service_name=None,
            email=None,
            aliases=["cdn.example.com"],
            ssl_mode="manual",
            ssl_cert_path=str(cert_path),
            ssl_key_path=str(key_path),
        )

        config_text = (self.config.nginx_available_dir / "secure.example.com").read_text(encoding="utf-8")
        commands = [entry["command"] for entry in self.system.commands]
        status = self.site_service.get_status("secure.example.com")

        self.assertEqual(record.ssl_mode.value, "manual")
        self.assertIn("ssl_certificate", config_text)
        self.assertIn(str(cert_path), config_text)
        self.assertNotIn(["certbot", "--nginx", "-d", "secure.example.com", "--non-interactive", "--agree-tos", "-m", "", "--redirect"], commands)
        self.assertEqual(status.ssl_mode, "manual")
        self.assertTrue(status.cert_exists)

    def test_renew_rejects_manual_certificate_site(self) -> None:
        cert_path = Path(self.temp_dir.name) / "manual.pem"
        key_path = Path(self.temp_dir.name) / "manual.key"
        cert_path.write_text("cert", encoding="utf-8")
        key_path.write_text("key", encoding="utf-8")
        self.site_service.create_site(
            domain="manual.example.com",
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

        with self.assertRaises(SiteCtlError):
            self.site_service.renew_certificates("manual.example.com")

    def test_get_certificate_info_reports_manual_certificate_details(self) -> None:
        cert_path = Path(self.temp_dir.name) / "inspect.pem"
        key_path = Path(self.temp_dir.name) / "inspect.key"
        cert_path.write_text("cert", encoding="utf-8")
        key_path.write_text("key", encoding="utf-8")
        self.site_service.create_site(
            domain="inspect.example.com",
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

        with patch.object(
            self.site_service.certificate_service,
            "_decode_certificate",
            return_value={
                "subject": ((("commonName", "inspect.example.com"),),),
                "issuer": ((("organizationName", "Cloudflare"),),),
                "notBefore": "Jan 01 00:00:00 2026 GMT",
                "notAfter": "Jan 01 00:00:00 2030 GMT",
            },
        ):
            info = self.site_service.get_certificate_info("inspect.example.com")

        self.assertEqual(info.ssl_mode, "manual")
        self.assertEqual(info.subject, "commonName=inspect.example.com")
        self.assertEqual(info.issuer, "organizationName=Cloudflare")
        self.assertEqual(info.cert_path, str(cert_path))
        self.assertTrue(info.exists)
        self.assertIsNotNone(info.days_remaining)

    def test_list_expiring_certificates_includes_missing_manual_certificate(self) -> None:
        cert_path = Path(self.temp_dir.name) / "missing.pem"
        key_path = Path(self.temp_dir.name) / "missing.key"
        cert_path.write_text("cert", encoding="utf-8")
        key_path.write_text("key", encoding="utf-8")
        self.site_service.create_site(
            domain="expiring.example.com",
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
        cert_path.unlink()

        items = self.site_service.list_expiring_certificates(days=30)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].domain, "expiring.example.com")
        self.assertFalse(items[0].exists)
        self.assertEqual(items[0].ssl_mode, "manual")

    def test_verify_certificate_confirms_matching_manual_cert_and_key(self) -> None:
        cert_path = Path(self.temp_dir.name) / "verify.pem"
        key_path = Path(self.temp_dir.name) / "verify.key"
        cert_path.write_text("shared-public-material", encoding="utf-8")
        key_path.write_text("shared-public-material", encoding="utf-8")
        self.site_service.create_site(
            domain="verify.example.com",
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

        result = self.site_service.verify_certificate("verify.example.com")

        self.assertTrue(result.cert_exists)
        self.assertTrue(result.key_exists)
        self.assertTrue(result.matches)
        self.assertEqual(result.detail, "certificate and private key match")

    def test_replace_manual_certificate_updates_state_and_reloads_nginx(self) -> None:
        cert_path = Path(self.temp_dir.name) / "initial.pem"
        key_path = Path(self.temp_dir.name) / "initial.key"
        new_cert_path = Path(self.temp_dir.name) / "replacement.pem"
        new_key_path = Path(self.temp_dir.name) / "replacement.key"
        cert_path.write_text("initial", encoding="utf-8")
        key_path.write_text("initial", encoding="utf-8")
        new_cert_path.write_text("replacement", encoding="utf-8")
        new_key_path.write_text("replacement", encoding="utf-8")
        self.site_service.create_site(
            domain="replace.example.com",
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
        self.system.commands.clear()

        record = self.site_service.replace_manual_certificate(
            "replace.example.com",
            ssl_cert_path=str(new_cert_path),
            ssl_key_path=str(new_key_path),
        )

        config_text = (self.config.nginx_available_dir / "replace.example.com").read_text(encoding="utf-8")
        state_payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        commands = [entry["command"] for entry in self.system.commands]

        self.assertEqual(record.ssl_cert_path, str(new_cert_path))
        self.assertEqual(record.ssl_key_path, str(new_key_path))
        self.assertIn(str(new_cert_path), config_text)
        self.assertIn(str(new_key_path), config_text)
        self.assertEqual(state_payload["sites"][0]["ssl_cert_path"], str(new_cert_path))
        self.assertEqual(state_payload["sites"][0]["ssl_key_path"], str(new_key_path))
        self.assertIn(["nginx", "-t"], commands)
        self.assertIn(["systemctl", "reload", "nginx"], commands)

    def test_replace_manual_certificate_rejects_non_manual_site(self) -> None:
        self.site_service.create_site(
            domain="replace.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
        )
        cert_path = Path(self.temp_dir.name) / "new.pem"
        key_path = Path(self.temp_dir.name) / "new.key"
        cert_path.write_text("new", encoding="utf-8")
        key_path.write_text("new", encoding="utf-8")

        with self.assertRaises(SiteCtlError):
            self.site_service.replace_manual_certificate(
                "replace.example.com",
                ssl_cert_path=str(cert_path),
                ssl_key_path=str(key_path),
            )

    def test_remove_systemd_site_stops_service(self) -> None:
        self.site_service.create_site(
            domain="svc.example.com",
            site_type="systemd",
            root=None,
            port=9000,
            pm2_name=None,
            service_name="svc-app",
            email="ops@example.com",
            aliases=None,
        )

        self.site_service.remove_site("svc.example.com")

        commands = [entry["command"] for entry in self.system.commands]
        self.assertIn(["systemctl", "stop", "svc-app"], commands)
        self.assertNotIn("svc-app", self.system.systemd_services)

    def test_get_logs_reads_systemd_logs(self) -> None:
        self.site_service.create_site(
            domain="svc.example.com",
            site_type="systemd",
            root=None,
            port=9000,
            pm2_name=None,
            service_name="svc-app",
            email="ops@example.com",
            aliases=None,
        )

        result = self.site_service.get_logs("svc.example.com", "systemd", lines=25)

        self.assertEqual(result.source, "systemd:svc-app")
        self.assertIn("svc-app: log1", result.content)

    def test_healthcheck_reports_local_and_remote_http(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/health":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"ok")
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]

        try:
            self.site_service.create_site(
                domain="health.example.com",
                site_type="proxy",
                root=None,
                port=port,
                pm2_name=None,
                service_name=None,
                email="ops@example.com",
                aliases=None,
            )

            report = self.site_service.run_healthcheck(
                "health.example.com",
                path="/health",
                timeout=2.0,
                remote_url=f"http://127.0.0.1:{port}/health",
            )
        finally:
            server.shutdown()
            server.server_close()

        probes = {probe.name: probe for probe in report.probes}
        self.assertTrue(probes["local_tcp"].ok)
        self.assertTrue(probes["local_http"].ok)
        self.assertTrue(probes["remote_https"].ok)

    def test_run_doctor_reports_expected_checks(self) -> None:
        self.config.nginx_available_dir.mkdir(parents=True, exist_ok=True)
        self.config.nginx_enabled_dir.mkdir(parents=True, exist_ok=True)
        self.config.nginx_main_config.parent.mkdir(parents=True, exist_ok=True)
        self.config.nginx_main_config.write_text(
            f"include {self.config.nginx_enabled_dir}/*;\n",
            encoding="utf-8",
        )

        report = self.site_service.run_doctor()

        names = {check.name for check in report.checks}
        self.assertIn("command:nginx", names)
        self.assertIn("command:certbot", names)
        self.assertIn("command:ip", names)
        self.assertIn("command:systemctl", names)
        self.assertIn("command:journalctl", names)
        self.assertIn("nginx:include-sites-enabled", names)
        self.assertIn("network:global-ipv6", names)
        self.assertIn("port6:80", names)
        self.assertIn("path:state-parent", names)
        self.assertTrue(report.advice)
        self.assertIn("AAAA", report.advice[0].detail)

    def test_run_doctor_with_domain_reports_aaaa_readiness_advice(self) -> None:
        with patch.object(self.doctor_service, "_resolve_domain_aaaa", return_value=[]):
            report = self.site_service.run_doctor(
                domain="home.example.com",
                site_type="proxy",
                port=8080,
                upstream_host="::1",
                listen_ipv6=True,
                email="ops@example.com",
                ssl_mode="letsencrypt",
            )

        names = {check.name for check in report.checks}
        self.assertIn("dns:aaaa:home.example.com", names)
        self.assertTrue(report.advice)
        aaa_advice = next(item for item in report.advice if item.title == "AAAA record still needs setup")
        self.assertIn("home.example.com", aaa_advice.detail)
        self.assertTrue(any("--listen-ipv6" in command for command in aaa_advice.commands))

    def test_export_and_import_round_trip(self) -> None:
        self.site_service.create_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=["www.example.com"],
        )

        export_path = Path(self.temp_dir.name) / "bundle.json"
        exported = self.site_service.export_sites(str(export_path))
        bundle = json.loads(export_path.read_text(encoding="utf-8"))

        self.assertEqual(exported, str(export_path))
        self.assertEqual(bundle["sites"][0]["aliases"], ["www.example.com"])
        self.assertIn("api.example.com", bundle["nginx_configs"])

        second_temp = tempfile.TemporaryDirectory()
        try:
            temp_path = Path(second_temp.name)
            config = SiteCtlConfig(
                nginx_available_dir=temp_path / "sites-available",
                nginx_enabled_dir=temp_path / "sites-enabled",
                nginx_snippets_dir=temp_path / "snippets",
                nginx_main_config=temp_path / "nginx" / "nginx.conf",
                cert_live_dir=temp_path / "letsencrypt" / "live",
                state_file=temp_path / "etc" / "sitectl" / "sites.json",
                log_dir=temp_path / "logs",
                templates_dir=Path(__file__).resolve().parents[1] / "sitectl" / "templates",
            )
            system = FakeSystemService()
            nginx_service = NginxService(config, system)
            certbot_service = CertbotService(system)
            pm2_service = PM2Service(system)
            systemd_service = SystemdService(system)
            status_service = StatusService(config, nginx_service, pm2_service, systemd_service)
            log_service = LogService(system, systemd_service)
            doctor_service = DoctorService(config, system)
            healthcheck_service = HealthcheckService()
            certificate_service = CertificateService(config)
            imported_service = SiteService(
                config,
                nginx_service,
                certbot_service,
                pm2_service,
                status_service,
                log_service,
                doctor_service,
                systemd_service,
                healthcheck_service,
                certificate_service,
            )

            preview = imported_service.import_sites(str(export_path), dry_run=True)
            self.assertIn("restore Nginx config for api.example.com", preview.actions)
            self.assertFalse(config.state_file.exists())

            result = imported_service.import_sites(str(export_path), force=True)
            self.assertIn("Imported 1 site(s)", result)
            restored_state = json.loads(config.state_file.read_text(encoding="utf-8"))
            restored_config = (config.nginx_available_dir / "api.example.com").read_text(encoding="utf-8")
            self.assertEqual(restored_state["sites"][0]["aliases"], ["www.example.com"])
            self.assertIn("server_name api.example.com www.example.com;", restored_config)
        finally:
            second_temp.cleanup()

    def test_history_and_rollback_restore_previous_config_and_state(self) -> None:
        self.site_service.create_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=["www.example.com"],
        )

        updated = self.site_service.update_site(
            domain="api.example.com",
            site_type="proxy",
            root=None,
            port=9090,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=["admin.example.com"],
        )
        self.assertEqual(updated.port, 9090)

        backups = self.site_service.list_history("api.example.com")
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].has_metadata)

        preview = self.site_service.rollback_site("api.example.com", backups[0].name, dry_run=True)
        self.assertIn("restore Nginx config", preview.actions[1])

        result = self.site_service.rollback_site("api.example.com", backups[0].name)
        self.assertIn("Rolled back api.example.com", result)

        state_payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        config_text = (self.config.nginx_available_dir / "api.example.com").read_text(encoding="utf-8")
        self.assertEqual(state_payload["sites"][0]["port"], 8080)
        self.assertEqual(state_payload["sites"][0]["aliases"], ["www.example.com"])
        self.assertIn("proxy_pass http://127.0.0.1:8080;", config_text)
        self.assertIn("server_name api.example.com www.example.com;", config_text)

    def test_rollback_restores_pm2_runtime_for_node_site(self) -> None:
        app_root = Path(self.temp_dir.name) / "rollback-node-app"
        app_root.mkdir(parents=True, exist_ok=True)
        (app_root / "package.json").write_text(
            json.dumps({"name": "rollback-node-app", "scripts": {"start": "node server.js"}}),
            encoding="utf-8",
        )

        self.site_service.create_site(
            domain="node.example.com",
            site_type="node",
            root=str(app_root),
            port=3000,
            pm2_name="rollback-node",
            service_name=None,
            email="ops@example.com",
            aliases=None,
        )
        self.assertIn("rollback-node", self.system.pm2_processes)

        self.site_service.update_site(
            domain="node.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
        )
        self.assertNotIn("rollback-node", self.system.pm2_processes)

        backups = self.site_service.list_history("node.example.com")
        self.site_service.rollback_site("node.example.com", backups[0].name)

        restored_state = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        self.assertEqual(restored_state["sites"][0]["type"], "node")
        self.assertEqual(restored_state["sites"][0]["port"], 3000)
        self.assertIn("rollback-node", self.system.pm2_processes)

    def test_rollback_restores_systemd_runtime(self) -> None:
        self.site_service.create_site(
            domain="svc.example.com",
            site_type="systemd",
            root=None,
            port=9000,
            pm2_name=None,
            service_name="rollback-svc",
            email="ops@example.com",
            aliases=None,
        )
        self.assertIn("rollback-svc", self.system.systemd_services)

        self.site_service.update_site(
            domain="svc.example.com",
            site_type="proxy",
            root=None,
            port=8080,
            pm2_name=None,
            service_name=None,
            email="ops@example.com",
            aliases=None,
        )
        self.assertNotIn("rollback-svc", self.system.systemd_services)

        backups = self.site_service.list_history("svc.example.com")
        self.site_service.rollback_site("svc.example.com", backups[0].name)

        restored_state = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        self.assertEqual(restored_state["sites"][0]["type"], "systemd")
        self.assertEqual(restored_state["sites"][0]["service_name"], "rollback-svc")
        self.assertIn("rollback-svc", self.system.systemd_services)


if __name__ == "__main__":
    unittest.main()
