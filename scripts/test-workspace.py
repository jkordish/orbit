"""Check the project map stays bounded, useful, and read-only."""

import contextlib
import io
import json
import shlex
import tempfile
from pathlib import Path
from unittest import mock

from orbit_core import cli, enter, git_status, workspace


def snapshot(root: Path) -> list[tuple[str, int]]:
    return sorted((str(path.relative_to(root)), path.stat().st_mtime_ns)
                  for path in root.rglob("*") if path.is_file() and not path.is_symlink())


with tempfile.TemporaryDirectory(prefix="orbit map ") as temporary:
    base = Path(temporary)
    source = base / "src"
    orbit = base / "orbit"
    source.mkdir()
    (orbit / "profiles").mkdir(parents=True)
    (orbit / "config").mkdir()
    (orbit / "config/profiles.txt").write_text("")
    rust = source / "alpha-rust"
    rust.mkdir()
    (rust / "Cargo.toml").write_text("[package]\nname = 'example'\n")
    node = source / "beta-node"
    node.mkdir()
    (node / "package.json").write_text(json.dumps({"engines": {"node": ">=24"}}))
    invalid = source / "gamma-invalid"
    invalid.mkdir()
    (invalid / ".orbit.json").write_text('{"version":1,"hooks":["run"]}')
    empty_git = source / "delta-empty-git"
    empty_git.mkdir()
    (empty_git / ".git").mkdir()
    (empty_git / ".git/HEAD").write_text("ref: refs/heads/main\n")
    ignored = source / "notes"
    ignored.mkdir()
    (ignored / "README.md").write_text("No project manifest here.\n")
    (source / "linked-rust").symlink_to(rust, target_is_directory=True)

    before = snapshot(source)
    checks = []

    def fake_probe(command, *arguments):
        checks.append((command, *arguments))
        if command == "rustup":
            return True, "stable-aarch64-apple-darwin (default)"
        if command == "node":
            return True, "v18.0.0"
        return False, "command unavailable"

    output = io.StringIO()
    with mock.patch.object(enter, "ORBIT_ROOT", orbit), mock.patch.object(enter, "probe", fake_probe), \
            contextlib.redirect_stdout(output):
        code = cli.main(["map", str(source), "--json"])
    assert code == 1
    report = json.loads(output.getvalue())
    assert report["command"] == "map" and report["schema_version"] == 1
    assert report["exit_code"] == code
    assert report["summary"] == "1 ready · 1 need attention · 2 review"
    projects = [row for row in report["rows"] if row["group"] == "Projects"]
    assert [(row["label"], row["state"]) for row in projects] == [
        ("alpha-rust", "READY"), ("beta-node", "ACTION"), ("delta-empty-git", "REVIEW"),
        ("gamma-invalid", "REVIEW"),
    ]
    assert "Node" in projects[1]["detail"]
    assert "No requirements" in projects[2]["detail"]
    assert "only version" in projects[3]["detail"]
    assert str(node) in report["next_action"]
    assert all(command in {"rustup", "node"} for command, *_ in checks)
    assert snapshot(source) == before, "workspace map changed a project file"

    def fake_git(project):
        if project == rust:
            return git_status.GitSnapshot("DIRTY", "branch main; local changes present", attention=True)
        return git_status.GitSnapshot("MATCH", "branch main; cached origin/main: commits match")

    with mock.patch.object(enter, "ORBIT_ROOT", orbit), mock.patch.object(enter, "probe", fake_probe), \
            mock.patch.object(workspace.git_status, "inspect", fake_git):
        combined = workspace.build_report(source, include_git=True)
    assert combined.next_action.startswith(f"git -C {shlex.quote(str(rust))}")
    assert "Git 3 cached matches, 1 attention" in combined.summary

    empty = workspace.build_report(ignored)
    assert empty.exit_code == 1 and empty.status == "REVIEW"

    with mock.patch.object(workspace, "MAX_PROJECTS", 2), mock.patch.object(enter, "ORBIT_ROOT", orbit), \
            mock.patch.object(enter, "probe", fake_probe):
        limited = workspace.build_report(source)
    assert any(row.group == "Coverage" and row.state == "REVIEW" for row in limited.rows)
    assert limited.exit_code == 1

    bad = io.StringIO()
    with contextlib.redirect_stdout(bad):
        code = cli.main(["map", str(base / "missing"), "--json"])
    assert code == 2 and json.loads(bad.getvalue())["status"] == "ERROR"

    repeated = io.StringIO()
    with contextlib.redirect_stdout(repeated):
        code = cli.main(["map", "--git", "--git", "--json"])
    assert code == 2 and json.loads(repeated.getvalue())["status"] == "ERROR"

print("Workspace map checked readiness, review, symlink exclusion, and no project writes.")
