"""Verify the prompt badge never executes helpers from an unrelated repository."""
import os
import subprocess
import tempfile
from pathlib import Path

import tomllib

root = Path(__file__).resolve().parents[1]
prompt = tomllib.loads((root / "config/starship.toml").read_text())
command = prompt["custom"]["orbit"]["command"]

with tempfile.TemporaryDirectory(prefix="dev machine prompt ") as temporary:
    base = Path(temporary)
    trusted = base / "trusted checkout"
    hostile = base / "untrusted checkout"
    marker = base / "called.txt"
    for checkout in (trusted, hostile):
        (checkout / "scripts").mkdir(parents=True)
        subprocess.run(
            ["git", "init", "--quiet", "--initial-branch=main"],
            cwd=checkout,
            check=True,
        )

    trusted_helper = trusted / "scripts/repository-status"
    trusted_helper.write_text(
        "#!/bin/bash\nprintf 'trusted\\n' >> \"$CALL_LOG\"\nprintf 'CLEAN\\tready\\n'\n"
    )
    trusted_helper.chmod(0o755)

    hostile_helper = hostile / "scripts/repository-status"
    hostile_helper.write_text(
        "#!/bin/bash\nprintf 'hostile\\n' >> \"$CALL_LOG\"\nprintf 'CLEAN\\tready\\n'\n"
    )
    hostile_helper.chmod(0o755)

    environment = dict(os.environ, ORBIT_ROOT=str(trusted.resolve()), CALL_LOG=str(marker))
    subprocess.run(["/bin/bash", "-c", command], cwd=hostile, env=environment, check=True)
    assert not marker.exists(), "the prompt ran a helper from the current project"

    subprocess.run(["/bin/bash", "-c", command], cwd=trusted, env=environment, check=True)
    assert marker.read_text() == "trusted\n", "the trusted orbit badge did not run"
print("Prompt status helper is restricted to the configured orbit checkout.")
