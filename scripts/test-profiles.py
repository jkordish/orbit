"""Exercise profile validation and keep per-machine choices out of tracked config."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

source = Path(__file__).resolve().parent / "profiles"
with tempfile.TemporaryDirectory(prefix="dev profiles ") as temp:
    root = Path(temp)
    (root / "scripts").mkdir()
    (root / "config").mkdir()
    shutil.copy2(source, root / "scripts/profiles")
    config = root / "config/profiles.txt"
    config.write_text("# shared defaults\n")

    def run(*args):
        return subprocess.run(
            ["/bin/bash", str(root / "scripts/profiles"), *args],
            capture_output=True, text=True, check=False,
        )

    assert run("--install").returncode == 0
    assert run("--select", "--profile", "cloud", "--profile", "../bad").returncode == 2
    assert config.read_text() == "# shared defaults\n"
    assert run("--select", "--profile").returncode == 2
    assert run("--select", "--profile", "cloud", "--profile", "infra", "--profile", "java").returncode == 0
    assert run("--select", "--profile", "cloud").returncode == 0
    assert config.read_text() == "# shared defaults\n"
    assert (root / ".state/profiles.txt").read_text() == "cloud\ninfra\njava\n"
    assert run("--validate").returncode == 0
    config.write_text("unknown\n")
    assert run("--validate").returncode == 2
print("Profile validation, persistence, and tracked-config preservation passed.")

with tempfile.TemporaryDirectory(prefix="orbit ai profiles ") as temp:
    root = Path(temp)
    for directory in ("scripts", "config", "bin"):
        (root / directory).mkdir()
    shutil.copy2(source, root / "scripts/profiles")
    config = root / "config/profiles.txt"
    config.write_text("# shared defaults\n")
    state = root / ".state/profiles.txt"
    log = root / "brew.log"
    brew = root / "bin/brew"
    brew.write_text(
        '#!/bin/bash\n'
        '[ "$1" != help ] || exit 1\n'
        'printf "%s\\n" "$@" >> "$ORBIT_TEST_BREW_LOG"\n'
        'exit "${ORBIT_TEST_BREW_EXIT:-0}"\n'
    )
    brew.chmod(0o755)
    env = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}",
               ORBIT_TEST_BREW_LOG=str(log))

    def run_ai(*args):
        return subprocess.run(
            ["/bin/bash", str(root / "scripts/profiles"), *args],
            capture_output=True, text=True, check=False, env=env,
        )

    result = run_ai("--validate", "--profile", "ai-dev")
    assert result.returncode == 0, result.stderr
    assert run_ai("--resolve").stdout == ""
    assert run_ai("--resolve", "--profile", "ai-dev").stdout == "ai-dev\n"
    all_profiles = run_ai("--resolve", "--profile", "all", "--profile", "ai-dev")
    assert all_profiles.returncode == 0, all_profiles.stderr
    assert all_profiles.stdout.splitlines().count("ai-dev") == 1
    listing = run_ai("--list")
    assert listing.returncode == 0, listing.stderr
    assert listing.stdout.startswith("Available: all, ai-dev autocomplete ")
    assert listing.stdout.endswith("\nEnabled:\n")
    assert not (root / ".state").exists()
    assert not log.exists()
    assert run_ai("--select", "--profile", "ai-dev", "--profile", "../bad").returncode == 2
    assert not (root / ".state").exists()
    assert run_ai("--select", "--profile", "cloud").returncode == 0
    assert run_ai("--select", "--profile", "ai-dev").returncode == 0
    assert run_ai("--select", "--profile", "ai-dev").returncode == 0
    assert state.read_text() == "cloud\nai-dev\n"
    assert config.read_text() == "# shared defaults\n"
    assert not log.exists()

    # Isolate the new profile; never invoke the real Homebrew executable.
    state.write_text("ai-dev\n")
    expected_file = f"--file={root.resolve() / 'profiles/ai-dev.Brewfile'}"
    for mode, expected in (
        ("--check", ["bundle", "check", expected_file]),
        ("--install", ["bundle", "install", expected_file, "--no-upgrade"]),
        ("--update", ["bundle", "install", expected_file]),
    ):
        log.write_text("")
        result = run_ai(mode)
        assert result.returncode == 0, result.stderr
        assert log.read_text().splitlines() == expected
        assert state.read_text() == "ai-dev\n"
    env["ORBIT_TEST_BREW_EXIT"] = "23"
    assert run_ai("--install").returncode == 23

    # The profile is declarative tooling, not an environment installer or model download.
    manifest = source.parent.parent / "profiles/ai-dev.Brewfile"
    declarations = [line.strip() for line in manifest.read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
    assert declarations == ['brew "duckdb"', 'brew "hf"', 'brew "hyperfine"']
print("AI development profile opt-in, deduplication, dispatch, and failure checks passed.")
