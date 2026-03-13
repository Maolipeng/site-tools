from __future__ import annotations

import json
import os
from pathlib import Path

from sitectl.exceptions import CommandExecutionError, ValidationError
from sitectl.services.system_service import SystemService


class PM2Service:
    def __init__(self, system_service: SystemService) -> None:
        self.system_service = system_service

    def _load_package_json(self, root: Path) -> dict[str, object]:
        package_json = root / "package.json"
        try:
            return json.loads(package_json.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValidationError(f"package.json not found in {root}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid package.json in {root}: {exc}") from exc

    def npm_install(self, root: Path) -> None:
        self.system_service.run(["npm", "install"], cwd=root)

    def build_if_present(self, root: Path) -> None:
        package_data = self._load_package_json(root)
        scripts = package_data.get("scripts")
        if isinstance(scripts, dict) and "build" in scripts:
            self.system_service.run(["npm", "run", "build"], cwd=root)

    def pm2_process_exists(self, pm2_name: str) -> bool:
        completed = self.system_service.run(["pm2", "jlist"], check=False)
        if completed.returncode != 0:
            return False
        try:
            processes = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            return False
        return any(item.get("name") == pm2_name for item in processes if isinstance(item, dict))

    def start_or_restart(self, pm2_name: str, root: Path, port: int) -> None:
        env = os.environ.copy()
        env["PORT"] = str(port)
        if self.pm2_process_exists(pm2_name):
            self.system_service.run(["pm2", "restart", pm2_name, "--update-env"], cwd=root, env=env)
            return
        self.system_service.run(
            ["pm2", "start", "npm", "--name", pm2_name, "--", "run", "start"],
            cwd=root,
            env=env,
        )

    def delete_process(self, pm2_name: str) -> None:
        self.system_service.run(["pm2", "delete", pm2_name])

