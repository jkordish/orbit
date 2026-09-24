"""Read-only readiness map of projects immediately below one source directory."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from . import enter
from .report import Report, Row

MAX_PROJECTS = 128
NEEDS_ATTENTION = {"MISSING", "MISMATCH", "SELECT"}


def default_source_root() -> Path:
    selected = os.environ.get("DEV_MACHINE_SRC_ROOT") or os.environ.get("ORBIT_SRC_ROOT")
    return Path(selected).expanduser().resolve() if selected else Path.home() / "src"


def _problem(report: Report) -> str:
    for row in report.rows:
        if row.state in NEEDS_ATTENTION | {"REVIEW"} and row.group == "Readiness":
            return f"{row.label}: {row.detail}"
    return report.next_action


def build_report(root: Path) -> Report:
    """Summarize each direct child project using ``enter``'s bounded scan."""
    children = sorted(
        (path for path in root.iterdir() if not path.name.startswith(".") and not path.is_symlink() and path.is_dir()),
        key=lambda path: (path.name.casefold(), path.name),
    )
    omitted = max(0, len(children) - MAX_PROJECTS)
    rows: list[Row] = []
    ready = attention = review = 0
    first_attention: Path | None = None
    first_review: Path | None = None
    for project in children[:MAX_PROJECTS]:
        try:
            inventory = enter.scan(project)
            stacks, declarations, findings = inventory
            manifest = project / ".orbit.json"
            git_marker = project / ".git"
            if not (stacks or declarations or findings or manifest.exists() or manifest.is_symlink()
                    or git_marker.exists() or git_marker.is_symlink()):
                continue
            result = enter.build_report(project, inventory=inventory)
        except (enter.InputError, OSError, UnicodeError, RuntimeError) as error:
            review += 1
            first_review = first_review or project
            rows.append(Row("Projects", "REVIEW", project.name, f"Declaration cannot be read: {error}"))
            continue
        tools = ", ".join(row.label for row in result.rows if row.group == "Stack" and row.state == "DETECTED")
        tools = tools or "Declared requirements"
        if result.exit_code == 0:
            ready += 1
            rows.append(Row("Projects", "READY", project.name, tools))
        else:
            has_missing = any(row.state in NEEDS_ATTENTION for row in result.rows)
            if has_missing:
                attention += 1
                state = "ACTION"
                first_attention = first_attention or project
            else:
                review += 1
                state = "REVIEW"
                first_review = first_review or project
            rows.append(Row("Projects", state, project.name, f"{tools} · {_problem(result)}"))
    if omitted:
        review += 1
        rows.append(Row("Coverage", "REVIEW", "Scan limit", f"{omitted} directories beyond the first {MAX_PROJECTS} were not inspected"))
    if not rows:
        rows.append(Row("Projects", "EMPTY", "No recognized projects", "Add a supported manifest or .orbit.json"))
    first_problem = first_attention or first_review
    if first_problem:
        action = f"./scripts/orbit enter {shlex.quote(str(first_problem))}"
    elif omitted:
        action = "Inspect a smaller source directory or use 'orbit enter' for an individual project."
    elif ready:
        action = "Open a project; run its own dependency and build checks when needed."
    else:
        action = "Add a supported project manifest or .orbit.json under this source directory."
    return Report(
        command="map", title="WORKSPACE MAP",
        status="ACTION NEEDED" if attention else "REVIEW" if review or not ready else "WORKSPACE READY",
        summary=f"{ready} ready · {attention} need attention · {review} review",
        next_action=action, exit_code=1 if attention or review or not ready else 0,
        notes=[f"Source root: {root}",
               "Read-only: bounded project declarations and local tool probes; project code is never run.",
               "Immediate child directories only; symbolic links skipped."],
        rows=rows,
    )
