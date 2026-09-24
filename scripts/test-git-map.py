"""Check the optional workspace Git view against isolated local repositories."""

import tempfile
from pathlib import Path
from unittest import mock

from orbit_core import enter, git_status, workspace


def git(*arguments: str) -> str:
    import subprocess

    result = subprocess.run(["git", *arguments], capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {arguments}: {result.stderr}"
    return result.stdout.strip()


def identity(project: Path) -> None:
    git("-C", str(project), "config", "user.name", "Orbit Test")
    git("-C", str(project), "config", "user.email", "orbit-test@example.invalid")


with tempfile.TemporaryDirectory(prefix="orbit git map ") as temporary:
    base = Path(temporary)
    source = base / "src"
    source.mkdir()
    remote = base / "remote.git"
    project = source / "main-project"
    git("init", "--bare", "--initial-branch=main", str(remote))
    git("init", "--initial-branch=main", str(project))
    identity(project)
    (project / "Cargo.toml").write_text("[package]\nname = 'example'\nversion = '0.1.0'\n")
    git("-C", str(project), "add", "Cargo.toml")
    git("-C", str(project), "commit", "-m", "Initial")
    git("-C", str(project), "remote", "add", "origin", str(remote))
    git("-C", str(project), "push", "-u", "origin", "main")
    assert git_status.inspect(project).state == "MATCH"

    orbit = base / "orbit"
    (orbit / "config").mkdir(parents=True)
    (orbit / "config/profiles.txt").write_text("")
    (orbit / "profiles").mkdir()
    with mock.patch.object(enter, "ORBIT_ROOT", orbit), \
            mock.patch.object(enter, "probe", return_value=(True, "stable-aarch64-apple-darwin (default)")):
        mapped = workspace.build_report(source, include_git=True)
    assert mapped.exit_code == 0
    assert any(row.group == "Git" and row.state == "MATCH" for row in mapped.rows)

    index = project / ".git/index"
    before_index = (index.read_bytes(), index.stat().st_mtime_ns)
    (project / "PRIVATE_LOCAL_NOTE.txt").write_text("Do not reveal this filename.\n")
    dirty = git_status.inspect(project)
    assert dirty.state == "DIRTY" and dirty.attention
    assert "PRIVATE_LOCAL_NOTE" not in dirty.detail
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before_index
    with mock.patch.object(enter, "ORBIT_ROOT", orbit), \
            mock.patch.object(enter, "probe", return_value=(True, "stable-aarch64-apple-darwin (default)")):
        mapped = workspace.build_report(source, include_git=True)
    assert mapped.exit_code == 1 and "git -C" in mapped.next_action
    assert "PRIVATE_LOCAL_NOTE" not in str(mapped.to_dict())
    (project / "PRIVATE_LOCAL_NOTE.txt").unlink()

    behind = base / "behind"
    git("clone", str(remote), str(behind))
    (project / "local.txt").write_text("local commit\n")
    git("-C", str(project), "add", "local.txt")
    git("-C", str(project), "commit", "-m", "Local")
    assert git_status.inspect(project).state == "AHEAD"

    peer = base / "peer"
    git("clone", str(remote), str(peer))
    identity(peer)
    (peer / "remote.txt").write_text("remote commit\n")
    git("-C", str(peer), "add", "remote.txt")
    git("-C", str(peer), "commit", "-m", "Remote")
    git("-C", str(peer), "push", "origin", "main")
    git("-C", str(behind), "fetch", "origin")
    assert git_status.inspect(behind).state == "BEHIND"
    git("-C", str(project), "fetch", "origin")
    assert git_status.inspect(project).state == "DIVERGED"

    git("-C", str(project), "worktree", "add", "-b", "feature", str(source / "worktree"))
    assert git_status.inspect(source / "worktree").state == "NO UPSTREAM"
    unsafe = source / "unsafe-marker"
    unsafe.mkdir()
    (unsafe / ".git").symlink_to(remote, target_is_directory=True)
    assert git_status.inspect(unsafe).state == "REVIEW"
    assert git_status.inspect(source).state == "NOT GIT"

print("Cached Git map checked clean, dirty, ahead, behind, diverged, worktree, and symlink states.")
