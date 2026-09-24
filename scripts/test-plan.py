"""Check the read-only plan and resume argument guard in an isolated home."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="orbit plan ") as temporary:
    base = Path(temporary)
    home = base / "home"
    root = base / "orbit"
    home.mkdir()
    (root / "scripts").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "profiles").mkdir()
    for filename in (
        "env.sh", "profiles", "configure", "configure.py", "plan",
        "orbit-python", "orbit_cli.py", "setup-ui.sh",
    ):
        shutil.copy2(source / "scripts" / filename, root / "scripts" / filename)
    shutil.copytree(source / "scripts/orbit_core", root / "scripts/orbit_core", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(source / "setup", root / "setup")
    for brewfile in (source / "profiles").glob("*.Brewfile"):
        shutil.copy2(brewfile, root / "profiles" / brewfile.name)
    for filename in ("shell.zsh", "gitconfig", "ssh.config", "starship.toml", "ghostty.conf"):
        shutil.copy2(source / "config" / filename, root / "config" / filename)
    (root / "config/profiles.txt").write_text("# no shared profiles\n")
    env = dict(os.environ, HOME=str(home))

    def run(script, *args):
        return subprocess.run(
            [str(root / script), *args], env=env, capture_output=True, text=True,
            check=False,
        )

    preview = run("scripts/plan", "--profile", "all", "--json")
    assert preview.returncode == 0, preview.stderr
    report = json.loads(preview.stdout)
    assert report["schema_version"] == 1
    assert sum(row["state"] == "SELECT" for row in report["rows"]) == 6
    assert any(row["group"] == "Managed files" for row in report["rows"])
    assert any(row["state"] == "CREATE" for row in report["rows"])
    assert not (root / ".state").exists()
    assert not (home / ".config").exists()

    invalid = run("scripts/plan", "--profile", "unknown")
    assert invalid.returncode == 2
    assert not (root / ".state").exists()

    catalog = run("scripts/profiles", "--verify-catalog")
    assert catalog.returncode == 0, catalog.stderr
    (root / "profiles/new.Brewfile").write_text("")
    assert run("scripts/profiles", "--verify-catalog").returncode == 2
    (root / "profiles/new.Brewfile").unlink()

    selected = run("scripts/profiles", "--select", "--profile", "cloud")
    assert selected.returncode == 0, selected.stderr
    preview = run("scripts/plan", "--profile", "all", "--json")
    assert preview.returncode == 0, preview.stderr
    report = json.loads(preview.stdout)
    assert any(row["state"] == "ENABLED" and row["label"] == "cloud" for row in report["rows"])
    assert sum(row["state"] == "SELECT" for row in report["rows"]) == 5

    (root / ".state/provision-state").write_text("phase=complete\n")
    resumed_with_profile = run("setup", "--resume", "--profile", "all")
    assert resumed_with_profile.returncode == 2
    assert "cannot select new profiles" in resumed_with_profile.stderr
    assert not (root / ".state/provision.lock").exists()
    resumed = run("setup", "--resume")
    assert resumed.returncode == 0, resumed.stderr
    assert "already complete" in resumed.stdout

print("Plan preview and resume guard passed without touching the real home.")
