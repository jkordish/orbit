"""Preserve user configuration while adding managed defaults once."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--plan", action="store_true", help="report managed file changes without writing")
plan_only = parser.parse_args().plan
planned_changes: list[tuple[str, Path, Path, bool]] = []
root = Path(os.environ["ORBIT_ROOT"])
home = Path.home()
backup = root / ".state/backups"
if (root / ".state").is_symlink() or backup.is_symlink():
    raise RuntimeError("Refusing to write backups through a symbolic link in .state/backups")
if not plan_only:
    backup.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup.chmod(0o700)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")

def target_path(path: Path) -> Path:
    if path.is_symlink():
        if not path.exists():
            raise RuntimeError(f"Refusing to replace dangling configuration symlink: {path}")
        return path.resolve(strict=True)
    return path


def backup_existing(path: Path, backup_name: str) -> None:
    if not path.exists():
        return
    if not path.is_file():
        raise RuntimeError(f"Refusing to replace non-file configuration: {path}")
    destination = backup / f"{backup_name}.{stamp}"
    suffix = 1
    while destination.exists():
        destination = backup / f"{backup_name}.{stamp}.{suffix}"
        suffix += 1
    shutil.copy2(path, destination)


def write_changed(
    path: Path,
    content: str,
    backup_name: str | None = None,
    mode: int | None = None,
) -> None:
    target = target_path(path)
    old = target.read_bytes() if target.exists() else None
    content_bytes = content.encode()
    old_mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else None
    target_mode = mode if mode is not None else (old_mode if old_mode is not None else 0o644)
    if old == content_bytes and old_mode == target_mode:
        return
    if plan_only:
        planned_changes.append(("CHANGE" if old is not None else "CREATE", path, target, old is not None))
        return
    if target.exists():
        backup_existing(target, backup_name or path.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content_bytes)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, target_mode)
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def ensure_line_last(
    path: Path,
    line: str,
    backup_name: str,
    mode: int | None = None,
    legacy_lines: tuple[str, ...] = (),
) -> None:
    target = target_path(path)
    old = target.read_text() if target.exists() else ""
    managed_lines = {line, *legacy_lines}
    lines = [item for item in old.splitlines() if item not in managed_lines]
    updated = "\n".join(lines)
    if updated:
        updated += "\n"
    updated += line + "\n"
    write_changed(path, updated, backup_name, mode)


def ensure_line_first(
    path: Path,
    line: str,
    backup_name: str,
    mode: int | None = None,
    legacy_lines: tuple[str, ...] = (),
) -> None:
    target = target_path(path)
    old = target.read_text() if target.exists() else ""
    managed_lines = {line, *legacy_lines}
    lines = [item for item in old.splitlines() if item not in managed_lines]
    updated = line + "\n" + "\n".join(lines)
    if lines:
        updated += "\n"
    write_changed(path, updated, backup_name, mode)


def ensure_homebrew_profile() -> None:
    path = home / ".zprofile"
    target = target_path(path)
    old = target.read_text() if target.exists() else ""
    legacy = 'eval "$(/opt/homebrew/bin/brew shellenv)"'
    block = """# >>> orbit Homebrew environment >>>
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi
# <<< orbit Homebrew environment <<<
"""
    block_lines = block.splitlines()
    lines = old.splitlines()
    found = next(
        (index for index in range(len(lines) - len(block_lines) + 1)
         if lines[index:index + len(block_lines)] == block_lines),
        None,
    )
    legacy_indexes = [index for index, line in enumerate(lines) if line == legacy]
    has_managed_markers = (
        "# >>> orbit Homebrew environment >>>" in lines
        or "# <<< orbit Homebrew environment <<<" in lines
    )
    if has_managed_markers and found is None:
        print("Retained customized Homebrew block in ~/.zprofile.")
        return
    if found is not None:
        if not legacy_indexes:
            return
        lines = [line for index, line in enumerate(lines) if index not in legacy_indexes]
        updated = "\n".join(lines) + "\n"
    elif legacy_indexes:
        first = legacy_indexes[0]
        lines = [line for index, line in enumerate(lines) if index not in legacy_indexes]
        lines[first:first] = block_lines
        updated = "\n".join(lines) + "\n"
    else:
        updated = old + ("" if not old or old.endswith("\n") else "\n") + block + "\n"
    write_changed(path, updated, "zprofile")


def preserve_zsh_history() -> None:
    old_history = home / ".zsh_history"
    state_home = Path(os.environ.get("XDG_STATE_HOME", str(home / ".local/state"))).expanduser()
    if not state_home.is_absolute() or not old_history.is_file():
        return
    managed_history = state_home / "zsh/history"
    if managed_history.exists() or managed_history.is_symlink():
        return
    if plan_only:
        planned_changes.append(("COPY", old_history, managed_history, False))
        return
    managed_history.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".history.", dir=managed_history.parent)
    os.close(descriptor)
    try:
        shutil.copy2(old_history, temporary_name)
        os.chmod(temporary_name, 0o600)
        try:
            os.link(temporary_name, managed_history)
        except FileExistsError:
            pass
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


managed_dir = home / ".config/orbit"
if not plan_only:
    managed_dir.mkdir(parents=True, exist_ok=True)
shell_source = root / "config/shell.zsh"
if shell_source.is_file():
    write_changed(managed_dir / "shell.zsh", shell_source.read_text(), "shell.zsh")
    write_changed(managed_dir / "root", f"{root}\n", "orbit-root", mode=0o600)
    ensure_line_last(
        home / ".zshrc",
        'source "$HOME/.config/orbit/shell.zsh"',
        "zshrc",
        legacy_lines=('source "$HOME/.config/dev-machine/shell.zsh"',),
    )
    preserve_zsh_history()
profile_files = (root / "config/profiles.txt", root / ".state/profiles.txt")
profile_names: list[str] = []
for profile_file in profile_files:
    if not profile_file.is_file():
        continue
    for name in profile_file.read_text().splitlines():
        name = name.strip()
        if name and not name.startswith("#") and name not in profile_names:
            profile_names.append(name)
write_changed(managed_dir / "enabled-profiles", "".join(name + chr(10) for name in profile_names), "enabled-profiles")
if shell_source.is_file():
    ensure_homebrew_profile()

write_changed(home / ".config/starship.toml", (root / "config/starship.toml").read_text())

managed = home / ".config/orbit/gitconfig"
write_changed(managed, (root / "config/gitconfig").read_text())

ssh_managed = home / ".config/orbit/ssh.config"
ssh_source = root / "config/ssh.config"
if ssh_source.is_file():
    write_changed(ssh_managed, ssh_source.read_text(), "ssh.config", mode=0o600)

ssh_config = home / ".ssh/config"
ssh_include = "Include ~/.config/orbit/ssh.config"
if ssh_source.is_file():
    ensure_line_first(
        ssh_config,
        ssh_include,
        "ssh-config",
        mode=0o600,
        legacy_lines=("Include ~/.config/dev-machine/ssh.config",),
    )

gitconfig = home / ".gitconfig"
old = gitconfig.read_text() if gitconfig.exists() else ""
include = '[include]\n    path = ~/.config/orbit/gitconfig\n'
managed_git_paths = {
    "path = ~/.config/dev-machine/gitconfig",
    "path = ~/.config/orbit/gitconfig",
}
git_lines = []
include_index = None
for line in old.splitlines():
    if line.strip() in managed_git_paths:
        if include_index is None:
            include_index = len(git_lines)
            git_lines.append("    path = ~/.config/orbit/gitconfig")
        continue
    git_lines.append(line)
if include_index is None:
    updated_gitconfig = include + old
else:
    updated_gitconfig = "\n".join(git_lines) + ("\n" if old.endswith("\n") else "")
if updated_gitconfig != old:
    write_changed(gitconfig, updated_gitconfig)

docker = home / ".docker/config.json"
data = json.loads(docker.read_text()) if docker.exists() else {}
plugins = data.setdefault("cliPluginsExtraDirs", [])
brew_prefix = Path(os.environ.get("HOMEBREW_PREFIX", "/opt/homebrew"))
docker_plugin_dir = str(brew_prefix / "lib/docker/cli-plugins")
if docker_plugin_dir not in plugins:
    plugins.append(docker_plugin_dir)
write_changed(docker, json.dumps(data, indent=2) + "\n")

# Keep other Ghostty settings intact and load the managed font fragment once.
ghostty_fragment = home / ".config/orbit/ghostty.conf"
write_changed(ghostty_fragment, (root / "config/ghostty.conf").read_text())
ghostty = home / "Library/Application Support/com.mitchellh.ghostty/config.ghostty"
old = ghostty.read_text() if ghostty.exists() else ""
font_include = f"config-file = {ghostty_fragment}"
legacy_font_include = f"config-file = {home / '.config' / 'dev-machine' / 'ghostty.conf'}"
ghostty_lines = [
    line for line in old.splitlines()
    if line not in {font_include, legacy_font_include}
]
updated_ghostty = "\n".join(ghostty_lines).rstrip()
if updated_ghostty:
    updated_ghostty += "\n"
updated_ghostty += font_include + "\n"
if updated_ghostty != old:
    write_changed(ghostty, updated_ghostty)

if plan_only:
    if not planned_changes:
        print("  No managed file changes.")
    for action, path, target, existing in planned_changes:
        destination = f"{path} -> {target}" if path != target else str(target)
        backup_note = " (backup before apply)" if existing else ""
        print(f"  {action:<6} {destination}{backup_note}")
