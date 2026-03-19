from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"


class InstallScriptTestCase(unittest.TestCase):
    def _write_fake_python(self, path: Path, version: str) -> None:
        path.write_text(
            """#!/usr/bin/env bash
set -euo pipefail
version="{version}"

if [[ "${{1:-}}" == "-V" ]]; then
  echo "Python $version"
  exit 0
fi

if [[ "${{1:-}}" == "-" ]]; then
  if [[ "$version" == "3.10.9" ]]; then
    exit 1
  fi
  exit 0
fi

if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "venv" ]]; then
  venv_dir="${{3:?missing venv path}}"
  mkdir -p "$venv_dir/bin"
  cp "$0" "$venv_dir/bin/python"
  chmod +x "$venv_dir/bin/python"
  exit 0
fi

echo "unexpected invocation: $*" >&2
exit 1
""".format(version=version),
            encoding="utf-8",
        )
        path.chmod(0o755)

    def test_install_script_prints_zshrc_path_hint_for_venv_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            venv_dir = Path(temp_dir) / "venv"
            completed = subprocess.run(
                [
                    "bash",
                    str(INSTALL_SCRIPT),
                    "--venv",
                    str(venv_dir),
                    "--no-test",
                ],
                cwd=REPO_ROOT,
                env={**os.environ, "AUTO_INSTALL_DEPS": "0"},
                text=True,
                capture_output=True,
                check=True,
            )

        self.assertIn("To add 'sitectl' to your zsh PATH permanently", completed.stdout)
        self.assertIn("# site-tools", completed.stdout)
        self.assertIn(f'export PATH="{venv_dir}/bin:$PATH"', completed.stdout)
        self.assertIn("[1/6] Checking system dependencies", completed.stdout)
        self.assertIn("[2/6] Selecting Python interpreter", completed.stdout)
        self.assertIn("[3/6] Creating virtual environment", completed.stdout)
        self.assertIn("[4/6] Linking launcher to the project source tree", completed.stdout)
        self.assertIn("[5/6] Skipping smoke test", completed.stdout)
        self.assertIn("[6/6] Finishing installation", completed.stdout)

    def test_install_script_help_mentions_interactive_mode(self) -> None:
        completed = subprocess.run(
            ["bash", str(INSTALL_SCRIPT), "--help"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("--interactive", completed.stdout)
        self.assertIn("Prompt for installation choices in the terminal", completed.stdout)

    def test_install_script_falls_back_to_python311_when_python3_is_too_old(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()

            python3 = fake_bin / "python3"
            python311 = fake_bin / "python3.11"
            self._write_fake_python(python3, "3.10.9")
            self._write_fake_python(python311, "3.11.9")

            venv_dir = temp_path / "venv"
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
            env["AUTO_INSTALL_DEPS"] = "0"
            env.pop("PYTHON_BIN", None)
            completed = subprocess.run(
                [
                    "bash",
                    str(INSTALL_SCRIPT),
                    "--venv",
                    str(venv_dir),
                    "--no-test",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn(f"Command path: {venv_dir}/bin/sitectl", completed.stdout)
            self.assertTrue((venv_dir / "bin" / "python").exists())
            self.assertIn("Using detected Python interpreter: python3.11", completed.stdout)

    def test_install_script_auto_installs_missing_system_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()
            install_log = temp_path / "install.log"

            self._write_fake_python(fake_bin / "python3", "3.11.9")

            (fake_bin / "apt-get").write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
printf 'apt-get %s\\n' "$*" >> "{install_log}"
""",
                encoding="utf-8",
            )
            (fake_bin / "sudo").write_text(
                """#!/usr/bin/env bash
set -euo pipefail
"$@"
""",
                encoding="utf-8",
            )
            (fake_bin / "npm").write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
printf 'npm %s\\n' "$*" >> "{install_log}"
""",
                encoding="utf-8",
            )
            for command in ("apt-get", "sudo", "npm"):
                (fake_bin / command).chmod(0o755)

            venv_dir = temp_path / "venv"
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
            env.pop("PYTHON_BIN", None)
            completed = subprocess.run(
                [
                    "bash",
                    str(INSTALL_SCRIPT),
                    "--venv",
                    str(venv_dir),
                    "--no-test",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )

            log_lines = install_log.read_text(encoding="utf-8").splitlines()
            self.assertIn("Missing system dependencies detected: nginx certbot node pm2", completed.stdout)
            self.assertIn("Installing system packages via apt: nginx certbot python3-certbot-nginx nodejs npm", completed.stdout)
            self.assertIn("Installing pm2 globally with npm", completed.stdout)
            self.assertIn("Requesting sudo privileges for: apt-get update", completed.stdout)
            self.assertIn("Requesting sudo privileges for: apt-get install -y nginx certbot python3-certbot-nginx nodejs npm", completed.stdout)
            self.assertIn("Requesting sudo privileges for: npm install -g pm2", completed.stdout)
            self.assertIn("If prompted, enter your sudo password to continue", completed.stdout)
            self.assertIn("apt-get update", log_lines)
            self.assertIn("apt-get install -y nginx certbot python3-certbot-nginx nodejs npm", log_lines)
            self.assertIn("npm install -g pm2", log_lines)
            self.assertIn(f"Command path: {venv_dir}/bin/sitectl", completed.stdout)


if __name__ == "__main__":
    unittest.main()
