from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sitectl.cli import build_parser, main
from sitectl.config import SiteCtlConfig
from sitectl.exceptions import ValidationError


class CliTestCase(unittest.TestCase):
    def test_build_parser_parses_create_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "create",
                "--domain",
                "app.example.com",
                "--type",
                "node",
                "--root",
                "/srv/app",
                "--port",
                "3000",
                "--pm2-name",
                "app",
                "--email",
                "ops@example.com",
            ]
        )
        self.assertEqual(args.command, "create")
        self.assertEqual(args.domain, "app.example.com")
        self.assertEqual(args.type, "node")
        self.assertEqual(args.port, 3000)

    def test_build_parser_parses_update_command_and_dry_run(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "update",
                "app.example.com",
                "--port",
                "4000",
                "--dry-run",
            ]
        )
        self.assertEqual(args.command, "update")
        self.assertEqual(args.domain, "app.example.com")
        self.assertEqual(args.port, 4000)
        self.assertTrue(args.dry_run)

    def test_build_parser_parses_logs_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["logs", "app.example.com", "--pm2", "--lines", "50"])
        self.assertEqual(args.command, "logs")
        self.assertEqual(args.domain, "app.example.com")
        self.assertTrue(args.pm2)
        self.assertEqual(args.lines, 50)

    def test_build_parser_parses_doctor_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        self.assertEqual(args.command, "doctor")

    def test_build_parser_parses_systemd_create_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "create",
                "--domain",
                "svc.example.com",
                "--type",
                "systemd",
                "--port",
                "9000",
                "--service-name",
                "svc-app",
                "--email",
                "ops@example.com",
            ]
        )
        self.assertEqual(args.type, "systemd")
        self.assertEqual(args.service_name, "svc-app")

    def test_build_parser_parses_alias_and_export_import_commands(self) -> None:
        parser = build_parser()
        create_args = parser.parse_args(
            [
                "create",
                "--domain",
                "app.example.com",
                "--type",
                "proxy",
                "--port",
                "8080",
                "--alias",
                "www.example.com",
                "--alias",
                "api.example.com",
                "--ssl-mode",
                "manual",
                "--ssl-cert",
                "/etc/ssl/certs/origin.pem",
                "--ssl-key",
                "/etc/ssl/private/origin.key",
                "--email",
                "ops@example.com",
            ]
        )
        export_args = parser.parse_args(["export", "--output", "/tmp/sites.json"])
        import_args = parser.parse_args(["import", "--input", "/tmp/sites.json", "--dry-run"])
        self.assertEqual(create_args.alias, ["www.example.com", "api.example.com"])
        self.assertEqual(create_args.ssl_mode, "manual")
        self.assertEqual(export_args.command, "export")
        self.assertEqual(import_args.command, "import")
        self.assertTrue(import_args.dry_run)

    def test_build_parser_parses_history_and_rollback_commands(self) -> None:
        parser = build_parser()
        history_args = parser.parse_args(["history", "app.example.com"])
        rollback_args = parser.parse_args(["rollback", "app.example.com", "--backup", "20260101010101", "--dry-run"])
        self.assertEqual(history_args.command, "history")
        self.assertEqual(rollback_args.command, "rollback")
        self.assertEqual(rollback_args.backup, "20260101010101")
        self.assertTrue(rollback_args.dry_run)

    def test_build_parser_parses_cert_commands(self) -> None:
        parser = build_parser()
        info_args = parser.parse_args(["cert-info", "app.example.com"])
        expiring_args = parser.parse_args(["cert-expiring", "--days", "14"])
        warn_args = parser.parse_args(["cert-warn", "--days", "7"])
        verify_args = parser.parse_args(["cert-verify", "app.example.com"])
        replace_args = parser.parse_args(
            [
                "cert-replace",
                "app.example.com",
                "--ssl-cert",
                "/etc/ssl/certs/new.pem",
                "--ssl-key",
                "/etc/ssl/private/new.key",
                "--dry-run",
            ]
        )
        self.assertEqual(info_args.command, "cert-info")
        self.assertEqual(expiring_args.command, "cert-expiring")
        self.assertEqual(expiring_args.days, 14)
        self.assertEqual(warn_args.command, "cert-warn")
        self.assertEqual(warn_args.days, 7)
        self.assertEqual(verify_args.command, "cert-verify")
        self.assertEqual(replace_args.command, "cert-replace")
        self.assertTrue(replace_args.dry_run)

    def test_build_parser_parses_healthcheck_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["healthcheck", "app.example.com", "--path", "/health", "--timeout", "2"])
        self.assertEqual(args.command, "healthcheck")
        self.assertEqual(args.path, "/health")
        self.assertEqual(args.timeout, 2.0)

    def test_build_parser_requires_domain_for_remove(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["remove"])
        self.assertEqual(ctx.exception.code, 2)

    @patch("sitectl.cli.build_site_service")
    @patch("sitectl.commands.create.run")
    def test_main_dispatches_create_handler(self, create_run: Mock, build_site_service: Mock) -> None:
        create_run.return_value = 0
        build_site_service.return_value = Mock()
        exit_code = main(
            [
                "create",
                "--domain",
                "app.example.com",
                "--type",
                "proxy",
                "--port",
                "8080",
                "--email",
                "ops@example.com",
            ]
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(create_run.called)

    @patch("sitectl.cli.build_site_service")
    def test_main_returns_non_zero_on_known_error(self, build_site_service: Mock) -> None:
        build_site_service.return_value = Mock()
        with patch("sitectl.commands.list_sites.run", side_effect=ValidationError("bad input")):
            stderr = io.StringIO()
            with patch("sys.stderr", stderr):
                exit_code = main(["list"])
        self.assertEqual(exit_code, 1)
        self.assertIn("bad input", stderr.getvalue())

    def test_config_from_env_overrides_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "custom-sites.json"
            with patch.dict(
                "os.environ",
                {
                    "SITECTL_STATE_FILE": str(state_file),
                },
                clear=False,
            ):
                config = SiteCtlConfig.from_env()
                self.assertEqual(config.state_file, state_file)


if __name__ == "__main__":
    unittest.main()
