from __future__ import annotations

import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REMOTE_INSTALL_SCRIPT = REPO_ROOT / "install.remote.sh"


class RemoteInstallScriptTestCase(unittest.TestCase):
    def _build_fake_archive(self, base_dir: Path, log_file: Path) -> Path:
        project_dir = base_dir / "site-tools-main"
        project_dir.mkdir()
        install_script = project_dir / "install.sh"
        install_script.write_text(
            f"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$@" > "{log_file}"
""",
            encoding="utf-8",
        )
        install_script.chmod(0o755)

        archive_path = base_dir / "sitectl.tar.gz"
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(project_dir, arcname=project_dir.name)
        return archive_path

    def test_remote_install_defaults_to_persistent_venv_and_no_editable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            home_dir = temp_path / "home"
            home_dir.mkdir()
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()
            log_file = temp_path / "install-args.log"
            archive_path = self._build_fake_archive(temp_path, log_file)

            (fake_bin / "curl").write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
cp "{archive_path}" "$4"
""",
                encoding="utf-8",
            )
            (fake_bin / "curl").chmod(0o755)

            completed = subprocess.run(
                ["bash", str(REMOTE_INSTALL_SCRIPT)],
                cwd=REPO_ROOT,
                env={
                    "HOME": str(home_dir),
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "SITECTL_ARCHIVE_URL": "https://example.com/sitectl.tar.gz",
                },
                text=True,
                capture_output=True,
                check=True,
            )

            install_args = log_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                install_args,
                ["--no-editable", "--venv", f"{home_dir}/.local/share/sitectl/venv"],
            )
            self.assertIn("[remote 1/4] Downloading sitectl archive", completed.stdout)
            self.assertIn("[remote 3/4] Running installer with persistent virtual environment", completed.stdout)

    def test_remote_install_preserves_explicit_mode_and_forces_no_editable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            home_dir = temp_path / "home"
            home_dir.mkdir()
            fake_bin = temp_path / "bin"
            fake_bin.mkdir()
            log_file = temp_path / "install-args.log"
            archive_path = self._build_fake_archive(temp_path, log_file)

            (fake_bin / "curl").write_text(
                f"""#!/usr/bin/env bash
set -euo pipefail
cp "{archive_path}" "$4"
""",
                encoding="utf-8",
            )
            (fake_bin / "curl").chmod(0o755)

            subprocess.run(
                ["bash", str(REMOTE_INSTALL_SCRIPT), "--user", "--interactive"],
                cwd=REPO_ROOT,
                env={
                    "HOME": str(home_dir),
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "SITECTL_ARCHIVE_URL": "https://example.com/sitectl.tar.gz",
                },
                text=True,
                capture_output=True,
                check=True,
            )

            install_args = log_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(install_args, ["--user", "--interactive", "--no-editable"])


if __name__ == "__main__":
    unittest.main()
