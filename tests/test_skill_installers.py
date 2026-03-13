from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "install-skill.sh"
UNINSTALL_SCRIPT = REPO_ROOT / "uninstall-skill.sh"


class SkillInstallerScriptsTestCase(unittest.TestCase):
    def test_install_skill_defaults_to_codex_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            env = os.environ.copy()
            env["HOME"] = str(temp_path / "home")
            env["CODEX_HOME"] = str(temp_path / "codex-home")

            subprocess.run(["bash", str(INSTALL_SCRIPT)], check=True, env=env, cwd=REPO_ROOT)

            installed_path = Path(env["CODEX_HOME"]) / "skills" / "sitectl-ops"
            self.assertTrue(installed_path.is_symlink())
            self.assertEqual(installed_path.resolve(), REPO_ROOT / "skills" / "sitectl-ops")

    def test_install_skill_supports_project_scope_for_claude_and_opencode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_root = temp_path / "demo-project"
            project_root.mkdir()
            env = os.environ.copy()
            env["HOME"] = str(temp_path / "home")
            env["XDG_CONFIG_HOME"] = str(temp_path / "xdg")

            subprocess.run(
                [
                    "bash",
                    str(INSTALL_SCRIPT),
                    "--target",
                    "claude",
                    "--target",
                    "opencode",
                    "--scope",
                    "project",
                    "--project-root",
                    str(project_root),
                ],
                check=True,
                env=env,
                cwd=REPO_ROOT,
            )

            claude_path = project_root / ".claude" / "skills" / "sitectl-ops"
            opencode_path = project_root / ".opencode" / "skills" / "sitectl-ops"
            self.assertTrue(claude_path.is_symlink())
            self.assertTrue(opencode_path.is_symlink())

    def test_install_skill_supports_openclaw_global_and_project_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            project_root = temp_path / "openclaw-project"
            project_root.mkdir()
            env = os.environ.copy()
            env["HOME"] = str(temp_path / "home")

            subprocess.run(
                ["bash", str(INSTALL_SCRIPT), "--target", "openclaw"],
                check=True,
                env=env,
                cwd=REPO_ROOT,
            )
            global_path = Path(env["HOME"]) / ".openclaw" / "skills" / "sitectl-ops"
            self.assertTrue(global_path.is_symlink())

            subprocess.run(
                [
                    "bash",
                    str(INSTALL_SCRIPT),
                    "--target",
                    "openclaw",
                    "--scope",
                    "project",
                    "--project-root",
                    str(project_root),
                ],
                check=True,
                env=env,
                cwd=REPO_ROOT,
            )
            project_path = project_root / "skills" / "sitectl-ops"
            self.assertTrue(project_path.is_symlink())

    def test_uninstall_skill_removes_requested_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            env = os.environ.copy()
            env["HOME"] = str(temp_path / "home")
            env["XDG_CONFIG_HOME"] = str(temp_path / "xdg")

            subprocess.run(
                ["bash", str(INSTALL_SCRIPT), "--target", "opencode"],
                check=True,
                env=env,
                cwd=REPO_ROOT,
            )
            installed_path = Path(env["XDG_CONFIG_HOME"]) / "opencode" / "skills" / "sitectl-ops"
            self.assertTrue(installed_path.exists())

            subprocess.run(
                ["bash", str(UNINSTALL_SCRIPT), "--target", "opencode"],
                check=True,
                env=env,
                cwd=REPO_ROOT,
            )
            self.assertFalse(installed_path.exists())


if __name__ == "__main__":
    unittest.main()
