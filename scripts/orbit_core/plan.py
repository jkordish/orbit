"""Read-only preview of profile selection and managed configuration."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from .report import Report, Row
from .state import resolve_profiles


class PlanError(Exception):
    """A managed-file preview could not be produced."""


def _managed_files(root: Path) -> list[Row]:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        result = subprocess.run(
            [str(root / "scripts/configure"), "--plan"], cwd=root, env=environment,
            capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PlanError("managed-file preview could not run") from error
    if result.returncode != 0:
        raise PlanError(result.stderr.strip() or "managed-file preview failed")
    rows: list[Row] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "No managed file changes.":
            rows.append(Row("Managed files", "UNCHANGED", "Managed configuration", "No file changes"))
        elif line.startswith(("CREATE ", "CHANGE ", "COPY ")):
            state, detail = line.split(None, 1)
            rows.append(Row("Managed files", state, "Destination", detail))
        else:
            rows.append(Row("Managed files", "NOTE", "Configurator", line))
    return rows or [Row("Managed files", "REVIEW", "Configurator", "No preview returned")]


def build_report(root: Path, arguments: list[str]) -> Report:
    existing = resolve_profiles(root, [])
    desired = resolve_profiles(root, arguments)
    rows: list[Row] = []
    for name in desired:
        rows.append(Row("Profiles", "ENABLED" if name in existing else "SELECT", name,
                        f"profiles/{name}.Brewfile"))
    if not desired:
        rows.append(Row("Profiles", "BASE", "Base Brewfile", "No optional profiles selected"))
    rows.extend(_managed_files(root))
    changes = sum(row.state in {"CREATE", "CHANGE", "COPY"} for row in rows)
    new_profiles = [name for name in desired if name not in existing]
    flags = " ".join(f"--profile {shlex.quote(name)}" for name in new_profiles)
    action = f"cd {shlex.quote(str(root))} && ./setup"
    if flags:
        action += f" {flags}"
    return Report(
        command="plan", title="PLAN", status="PREVIEW",
        summary=f"{len(new_profiles)} profile selections; {changes} managed file changes",
        next_action=action,
        notes=["Read-only preview of selected profiles and managed user files.",
               "Setup also installs packages and runtimes, applies macOS preferences, and starts services.",
               "File contents and backup contents are not displayed."],
        rows=rows,
    )
