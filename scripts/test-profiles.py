"""Exercise profile validation and keep per-machine choices out of tracked config."""
from pathlib import Path
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
