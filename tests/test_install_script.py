from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"


class InstallScriptTestCase(unittest.TestCase):
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
                text=True,
                capture_output=True,
                check=True,
            )

        self.assertIn("To add 'sitectl' to your zsh PATH permanently", completed.stdout)
        self.assertIn("# site-tools", completed.stdout)
        self.assertIn(f'export PATH="{venv_dir}/bin:$PATH"', completed.stdout)

    def test_install_script_falls_back_to_python311_when_python3_is_too_old(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()

            python3 = fake_bin / "python3"
            python311 = fake_bin / "python3.11"
            python_template = """#!/usr/bin/env bash
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
"""
            python3.write_text(python_template.format(version="3.10.9"))
            python311.write_text(python_template.format(version="3.11.9"))
            python3.chmod(0o755)
            python311.chmod(0o755)

            venv_dir = temp_path / "venv"
            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}:{env['PATH']}"
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


if __name__ == "__main__":
    unittest.main()
