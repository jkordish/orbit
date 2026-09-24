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
    (root / "config/shell.zsh").write_text("# managed shell\n")
    (root / "config/ssh.config").write_text("Host github.com\n    ForwardAgent no\n")
    (root / "config/starship.toml").write_text("add_newline = true\n")
    (home / ".config").mkdir()
    (home / ".config/starship.toml").write_text("# existing prompt\n")
    (root / "config/ghostty.conf").write_text("font-family = JetBrainsMono Nerd Font Mono\n")
    legacy_git_include = "[include]\n    path = ~/.config/dev-machine/gitconfig\n"
    original_git = "[user]\n    name = Existing User\n[pull]\n    ff = false\n"
    (home / ".gitconfig").write_text(legacy_git_include + original_git)
    (home / ".zshrc").write_text(
        'source "$HOME/.config/dev-machine/shell.zsh"\n# User shell settings\n'
    )
    (home / ".ssh").mkdir()
    (home / ".ssh/config").write_text(
        "Include ~/.config/dev-machine/ssh.config\nHost github.com\n    ForwardAgent no\n"
    )
    ghostty = home / "Library/Application Support/com.mitchellh.ghostty/config.ghostty"
    ghostty.parent.mkdir(parents=True)
    ghostty.write_text(
        "config-file = " + str(home / ".config/dev-machine/ghostty.conf")
        + "\nfont-size = 14\n"
    )
    docker = home / ".docker/config.json"
    docker.write_text(json.dumps({"credsStore": "desktop", "cliPluginsExtraDirs": ["/custom"]}))
    env = dict(os.environ, HOME=str(home), ORBIT_ROOT=str(root))
    preview = subprocess.run(
        [sys.executable, str(script), "--plan"],
        env=env, check=True, capture_output=True, text=True,
    )
    assert "CHANGE" in preview.stdout
    assert str(home / ".gitconfig") in preview.stdout
    assert not (root / ".state").exists()
    assert not (home / ".config/orbit").exists()
    assert (home / ".gitconfig").read_text() == legacy_git_include + original_git
    assert docker.read_text() == json.dumps(
        {"credsStore": "desktop", "cliPluginsExtraDirs": ["/custom"]}
    )
    subprocess.run([sys.executable, str(script)], env=env, check=True)
    assert (home / ".config/starship.toml").read_text() == "add_newline = true\n"
    assert any(p.read_text() == "# existing prompt\n" for p in (root / ".state/backups").glob("starship.toml.*"))
    first_git = (home / ".gitconfig").read_text()
    first_docker = docker.read_text()
    assert original_git in first_git
    assert first_git.count("path = ~/.config/orbit/gitconfig") == 1
    assert "dev-machine" not in first_git
    first_zshrc = (home / ".zshrc").read_text()
    assert 'source "$HOME/.config/orbit/shell.zsh"' in first_zshrc
    assert "dev-machine" not in first_zshrc
    first_ssh = (home / ".ssh/config").read_text()
    assert first_ssh.splitlines()[0] == "Include ~/.config/orbit/ssh.config"
    assert "dev-machine" not in first_ssh
    first_ghostty = ghostty.read_text()
    assert str(home / ".config/orbit/ghostty.conf") in first_ghostty
    assert "dev-machine" not in first_ghostty
    assert "font-size = 14" in first_ghostty
    assert json.loads(first_docker)["credsStore"] == "desktop"
    assert json.loads(first_docker)["cliPluginsExtraDirs"] == [
        "/custom", "/opt/homebrew/lib/docker/cli-plugins"
    ]
    subprocess.run([sys.executable, str(script)], env=env, check=True)
    assert (home / ".gitconfig").read_text() == first_git
    assert (home / ".zshrc").read_text() == first_zshrc
    assert (home / ".ssh/config").read_text() == first_ssh
    assert ghostty.read_text() == first_ghostty
    assert docker.read_text() == first_docker
    assert len(list((root / ".state/backups").iterdir())) == 6
    settled_preview = subprocess.run(
        [sys.executable, str(script), "--plan"],
        env=env, check=True, capture_output=True, text=True,
    )
    assert "No managed file changes" in settled_preview.stdout
    assert len(list((root / ".state/backups").iterdir())) == 6
print("Configuration preserves existing values and is idempotent.")
