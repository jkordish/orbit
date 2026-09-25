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
        "orbit", "orbit-python", "orbit_cli.py", "setup-ui.sh",
    ):
        shutil.copy2(source / "scripts" / filename, root / "scripts" / filename)
    shutil.copytree(source / "scripts/orbit_core", root / "scripts/orbit_core", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(source / "setup", root / "setup")
    for brewfile in (source / "profiles").glob("*.Brewfile"):
        shutil.copy2(brewfile, root / "profiles" / brewfile.name)
    profile_count = len(list((root / "profiles").glob("*.Brewfile")))
    for filename in ("shell.zsh", "gitconfig", "ssh.config", "starship.toml", "ghostty.conf"):
        shutil.copy2(source / "config" / filename, root / "config" / filename)
    (root / "config/profiles.txt").write_text("# no shared profiles\n")
    env = dict(os.environ, HOME=str(home))
    env.pop("ORBIT_SETUP_ENTRYPOINT", None)

    def run(script, *args):
        return subprocess.run(
            [str(root / script), *args], env=env, capture_output=True, text=True,
            check=False,
        )

    direct_help = run("setup", "--help")
    assert direct_help.returncode == 0
    assert direct_help.stdout.startswith("Usage: ./setup ")
    orbit_help = run("scripts/orbit", "provision", "--help")
    assert orbit_help.returncode == 0
    assert orbit_help.stdout.startswith("Usage: orbit provision ")
    assert "Usage: ./setup" not in orbit_help.stdout
    invalid_preview = run("scripts/orbit", "provision", "--preview-ui", "--resume")
    assert invalid_preview.returncode == 2
    assert "Usage: orbit provision --preview-ui" in invalid_preview.stderr
    orbit_preview = run("scripts/orbit", "provision", "--preview-ui")
    assert orbit_preview.returncode == 0
    assert "orbit provision --resume" in orbit_preview.stdout
    direct_preview = run("setup", "--preview-ui")
    assert direct_preview.returncode == 0
    assert "./setup --resume" in direct_preview.stdout

    preview = run("scripts/plan", "--profile", "all", "--json")
    assert preview.returncode == 0, preview.stderr
    report = json.loads(preview.stdout)
    assert report["schema_version"] == 1
    assert report["next_action"].startswith("orbit provision --profile ")
    assert sum(row["state"] == "SELECT" for row in report["rows"]) == profile_count
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
    assert sum(row["state"] == "SELECT" for row in report["rows"]) == profile_count - 1

    (root / ".state/provision-state").write_text("phase=complete\n")
    resumed_with_profile = run("setup", "--resume", "--profile", "all")
    assert resumed_with_profile.returncode == 2
    assert "cannot select new profiles" in resumed_with_profile.stderr
    assert not (root / ".state/provision.lock").exists()
    resumed = run("setup", "--resume")
    assert resumed.returncode == 0, resumed.stderr
    assert "use ./setup" in resumed.stdout
    orbit_resumed = run("scripts/orbit", "provision", "--resume")
    assert orbit_resumed.returncode == 0, orbit_resumed.stderr
    assert "use orbit provision" in orbit_resumed.stdout

print("Plan preview, command guidance, and resume guard passed without touching the real home.")
