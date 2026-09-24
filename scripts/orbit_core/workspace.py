"""Read-only readiness map of projects immediately below one source directory."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from . import enter, git_status
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


def _project_list(verb: str, projects: list[str]) -> str:
    shown = ", ".join(projects[:3])
    more = f" (+{len(projects) - 3} more)" if len(projects) > 3 else ""
    word = "project" if len(projects) == 1 else "projects"
    return f"{verb} {len(projects)} {word}: {shown}{more}"


def build_report(root: Path, *, include_git: bool = False, include_needs: bool = False) -> Report:
    """Summarize each direct child project using ``enter``'s bounded scan."""
    children = sorted(
        (path for path in root.iterdir() if not path.name.startswith(".") and not path.is_symlink() and path.is_dir()),
        key=lambda path: (path.name.casefold(), path.name),
    )
    omitted = max(0, len(children) - MAX_PROJECTS)
    rows: list[Row] = []
    git_rows: list[Row] = []
    stack_projects: dict[str, list[str]] = {}
    profile_projects: dict[str, list[str]] = {}
    unselected_profiles: set[str] = set()
    ready = attention = review = 0
    git_current = git_attention = git_review = git_other = 0
    first_attention: Path | None = None
    first_review: Path | None = None
    first_git_critical: Path | None = None
    first_git_attention: Path | None = None
    first_git_review: Path | None = None

    def record_git(project: Path) -> None:
        nonlocal git_current, git_attention, git_review, git_other
        nonlocal first_git_critical, first_git_attention, first_git_review
        if not include_git:
            return
        try:
            snapshot = git_status.inspect(project)
        except (OSError, RuntimeError) as error:
            snapshot = git_status.GitSnapshot("REVIEW", f"Git status unavailable: {error}", review=True)
        git_rows.append(Row("Git", snapshot.state, project.name, snapshot.detail))
        if snapshot.attention:
            git_attention += 1
            if snapshot.state in {"DIRTY", "DIVERGED", "AHEAD"}:
                first_git_critical = first_git_critical or project
            first_git_attention = first_git_attention or project
        elif snapshot.review:
            git_review += 1
            first_git_review = first_git_review or project
        elif snapshot.state == "MATCH":
            git_current += 1
        else:
            git_other += 1

    for project in children[:MAX_PROJECTS]:
        try:
            inventory = enter.scan(project)
            stacks, declarations, findings = inventory
            manifest = project / ".orbit.json"
            git_marker = project / ".git"
            if not (stacks or declarations or findings or manifest.exists() or manifest.is_symlink()
                    or git_marker.exists() or git_marker.is_symlink()):
                continue
        except (enter.InputError, OSError, UnicodeError, RuntimeError) as error:
            review += 1
            first_review = first_review or project
            rows.append(Row("Projects", "REVIEW", project.name, f"Declaration cannot be read: {error}"))
            record_git(project)
            continue
        if include_needs:
            for stack in stacks:
                stack_projects.setdefault(stack, []).append(project.name)
        record_git(project)
        try:
            result = enter.build_report(project, inventory=inventory)
        except (enter.InputError, OSError, UnicodeError, RuntimeError) as error:
            review += 1
            first_review = first_review or project
            rows.append(Row("Projects", "REVIEW", project.name, f"Declaration cannot be read: {error}"))
            continue
        if include_needs:
            for row in result.rows:
                if row.group == "Readiness" and row.label.startswith("profile/") \
                        and row.state in {"SELECT", "SELECTED"}:
                    name = row.label.removeprefix("profile/")
                    profile_projects.setdefault(name, []).append(project.name)
                    if row.state == "SELECT":
                        unselected_profiles.add(name)
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
    rows.extend(git_rows)
    if omitted:
        review += 1
        rows.append(Row("Coverage", "REVIEW", "Scan limit", f"{omitted} directories beyond the first {MAX_PROJECTS} were not inspected"))
    if not rows:
        rows.append(Row("Projects", "EMPTY", "No recognized projects", "Add a supported manifest or .orbit.json"))
    profile_plan = ""
    if include_needs:
        for name, projects in sorted(stack_projects.items(), key=lambda item: (-len(item[1]), item[0].casefold())):
            rows.append(Row("Project stacks", "DETECTED", name, _project_list("Detected in", projects)))
        if not stack_projects:
            rows.append(Row("Project stacks", "NONE", "No stacks",
                            "No recognized project stacks in inspected projects"))
        for name, projects in sorted(profile_projects.items()):
            rows.append(Row("Profile demand", "SELECT" if name in unselected_profiles else "SELECTED",
                            name, _project_list("Requested by", projects)))
        if unselected_profiles:
            flags = " ".join(f"--profile {shlex.quote(name)}" for name in sorted(unselected_profiles))
            profile_plan = f"cd {shlex.quote(str(enter.ORBIT_ROOT))} && ./scripts/orbit plan {flags}"
            rows.append(Row("Profile demand", "PREVIEW", "Selection plan", profile_plan))
        elif not profile_projects:
            rows.append(Row("Profile demand", "NONE", "No declarations",
                            "No valid explicit profile requests found in inspected projects"))
    if first_git_critical:
        action = f"git -C {shlex.quote(str(first_git_critical))} status --short --branch"
    elif profile_plan:
        action = profile_plan
    elif first_attention:
        action = f"./scripts/orbit enter {shlex.quote(str(first_attention))}"
    elif first_git_attention:
        action = f"git -C {shlex.quote(str(first_git_attention))} status --short --branch"
    elif first_review:
        action = f"./scripts/orbit enter {shlex.quote(str(first_review))}"
    elif first_git_review:
        action = f"git -C {shlex.quote(str(first_git_review))} status --short --branch"
    elif omitted:
        action = "Inspect a smaller source directory or use 'orbit enter' for an individual project."
    elif ready:
        action = "Open a project; run its own dependency and build checks when needed."
    else:
        action = "Add a supported project manifest or .orbit.json under this source directory."
    summary = f"{ready} ready · {attention} need attention · {review} review"
    notes = [f"Source root: {root}",
             "Read-only: bounded project declarations and local tool probes; project code is never run.",
             "Immediate child directories only; symbolic links skipped."]
    if include_git:
        summary += f" · Git {git_current} cached matches, {git_attention} attention, {git_review} review"
        if git_other:
            summary += f", {git_other} without checkout"
        notes.append("Git uses configured upstream and cached refs only; no fetch, sync, or publish.")
    if include_needs:
        summary += (f" · stacks {len(stack_projects)}, profiles {len(profile_projects)} "
                    f"({len(unselected_profiles)} unselected)")
        notes.append("Stacks come from recognized manifests; profiles come only from valid .orbit.json declarations in inspected projects.")
        notes.append("Selected profiles are choices, not proof their packages are installed.")
    return Report(
        command="map", title="WORKSPACE MAP",
        status="ACTION NEEDED" if attention or git_attention else "REVIEW" if review or git_review or not ready else "WORKSPACE READY",
        summary=summary,
        next_action=action, exit_code=1 if attention or review or not ready or git_attention or git_review else 0,
        notes=notes,
        rows=rows,
    )
