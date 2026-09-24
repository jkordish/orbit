"""Read-only Git snapshot for arbitrary projects, using cached refs only."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitSnapshot:
    state: str
    detail: str
    attention: bool = False
    review: bool = False


def _git(project: Path, *arguments: str) -> tuple[bool, str]:
    environment = dict(os.environ)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_NAMESPACE"):
        environment.pop(name, None)
    # Status may refresh the index; partial clones may fetch missing objects.
    environment.update({
        "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0",
    })
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "maintenance.auto=false",
             "-c", "gc.auto=0", "-C", str(project), *arguments],
            env=environment, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, errors="replace", check=False, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return result.returncode == 0, result.stdout.strip()


def inspect(project: Path) -> GitSnapshot:
    marker = project / ".git"
    if marker.is_symlink():
        return GitSnapshot("REVIEW", "Git marker is a symbolic link; skipped", review=True)
    if not marker.exists():
        return GitSnapshot("NOT GIT", "No Git checkout")
    ok, top = _git(project, "rev-parse", "--show-toplevel")
    if not ok or Path(top).resolve() != project.resolve():
        return GitSnapshot("REVIEW", "Git checkout could not be inspected safely", review=True)
    ok, changes = _git(project, "status", "--porcelain=v1", "--untracked-files=normal", "--ignore-submodules=none")
    if not ok:
        return GitSnapshot("REVIEW", "Git status unavailable", review=True)
    branch_ok, branch = _git(project, "symbolic-ref", "--quiet", "--short", "HEAD")
    if changes:
        where = f"branch {branch}" if branch_ok else "detached HEAD"
        return GitSnapshot("DIRTY", f"{where}; local changes present", attention=True)
    if not branch_ok:
        return GitSnapshot("DETACHED", "detached HEAD; clean working tree", review=True)
    upstream_ok, upstream = _git(project, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if not upstream_ok:
        return GitSnapshot("NO UPSTREAM", f"branch {branch}; no configured upstream", review=True)
    counts_ok, counts = _git(project, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    try:
        ahead, behind = (int(value) for value in counts.split())
    except ValueError:
        counts_ok = False
    if not counts_ok or ahead < 0 or behind < 0:
        return GitSnapshot("REVIEW", "Cached upstream comparison unavailable", review=True)
    detail = f"branch {branch}; cached {upstream}"
    if ahead and behind:
        return GitSnapshot("DIVERGED", f"{detail}: {ahead} ahead, {behind} behind", attention=True)
    if ahead:
        return GitSnapshot("AHEAD", f"{detail}: {ahead} local commit(s) ahead", attention=True)
    if behind:
        return GitSnapshot("BEHIND", f"{detail}: {behind} commit(s) behind", attention=True)
    return GitSnapshot("MATCH", f"{detail}: commits match")
