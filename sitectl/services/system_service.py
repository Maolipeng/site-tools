from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from sitectl.exceptions import CommandExecutionError


class SystemService:
    def command_exists(self, command: str) -> bool:
        return shutil.which(command) is not None

    def run(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CommandExecutionError(command, 127, message=f"Command not found: {command[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CommandExecutionError(command, 124, message=f"Command timed out: {' '.join(command)}") from exc

        if check and completed.returncode != 0:
            raise CommandExecutionError(command, completed.returncode, completed.stdout, completed.stderr)
        return completed

