"""Read-only access to the same profile selections used by setup."""

from __future__ import annotations

import subprocess
from pathlib import Path


class ProfileError(Exception):
    """The shared or local profile selection is invalid."""


def selected_profiles(root: Path) -> list[str]:
    names: list[str] = []
    for path in (root / "config/profiles.txt", root / ".state/profiles.txt"):
        if path.is_symlink() or not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if name and not name.startswith("#") and name not in names:
                names.append(name)
    return names


def resolve_profiles(root: Path, arguments: list[str]) -> list[str]:
    command = str(root / "scripts/profiles")
    for mode in ("--validate", "--resolve"):
        try:
            result = subprocess.run(
                [command, mode, *arguments], cwd=root, capture_output=True, text=True,
                check=False, timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProfileError("profile catalog could not be read") from error
        if result.returncode != 0:
            raise ProfileError(result.stderr.strip() or "invalid profile selection")
    return result.stdout.splitlines()
