from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
