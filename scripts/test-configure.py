"""Exercise preservation and idempotence using an isolated home, never the real one."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

script = Path(__file__).with_name("configure.py")
with tempfile.TemporaryDirectory() as temporary:
    base = Path(temporary)
    home = base / "home"
    root = base / "repo"
    (home / ".docker").mkdir(parents=True)
    (root / "config").mkdir(parents=True)
    (root / "config/gitconfig").write_text("[fetch]\n    prune = true\n")
    (root / "config/starship.toml").write_text("add_newline = true\n")
    (home / ".config").mkdir()
    (home / ".config/starship.toml").write_text("# existing prompt\n")
    (root / "config/ghostty.conf").write_text("font-family = JetBrainsMono Nerd Font Mono\n")
    original_git = "[user]\n    name = Existing User\n[pull]\n    ff = false\n"
    (home / ".gitconfig").write_text(original_git)
    docker = home / ".docker/config.json"
    docker.write_text(json.dumps({"credsStore": "desktop", "cliPluginsExtraDirs": ["/custom"]}))
    env = dict(os.environ, HOME=str(home), ORBIT_ROOT=str(root))
    subprocess.run([sys.executable, str(script)], env=env, check=True)
    assert (home / ".config/starship.toml").read_text() == "add_newline = true\n"
    assert any(p.read_text() == "# existing prompt\n" for p in (root / ".state/backups").glob("starship.toml.*"))
    first_git = (home / ".gitconfig").read_text()
    first_docker = docker.read_text()
    assert first_git.endswith(original_git)
    assert json.loads(first_docker)["credsStore"] == "desktop"
    assert json.loads(first_docker)["cliPluginsExtraDirs"] == [
        "/custom", "/opt/homebrew/lib/docker/cli-plugins"
    ]
    subprocess.run([sys.executable, str(script)], env=env, check=True)
    assert (home / ".gitconfig").read_text() == first_git
    assert docker.read_text() == first_docker
    assert len(list((root / ".state/backups").iterdir())) == 3
print("Configuration preserves existing values and is idempotent.")
