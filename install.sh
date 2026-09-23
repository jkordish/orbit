#!/bin/bash
set -euo pipefail

repository_url='https://github.com/jkordish/orbit.git'
install_root="${HOME:?HOME must be set}/.config/orbit"

usage() {
  cat <<'EOF'
Usage: install.sh [--resume] [--profile NAME]...

Clone or safely update Orbit at ~/.config/orbit, then run its full setup.
Run as your normal macOS user. Optional arguments are passed to ./setup.
EOF
}

hold() {
  printf 'ORBIT / INSTALLER\n  HOLD · %s\n' "$1" >&2
  exit 1
}

if [ "${1:-}" = --help ]; then
  usage
  exit 0
fi

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  hold 'This installer targets Apple Silicon macOS.'
fi
if [ "$(id -u)" -eq 0 ]; then
  hold 'Do not run as root or with sudo; use your normal account.'
fi

if ! xcode-select -p >/dev/null 2>&1; then
  xcode-select --install || true
  hold 'Finish the Apple Command Line Tools installer, then rerun the curl command.'
fi
command -v git >/dev/null 2>&1 || hold 'Git is unavailable; install Apple Command Line Tools and retry.'

mkdir -p "$HOME/.config"
if [ -L "$install_root" ]; then
  hold "$install_root is a symbolic link; refusing to follow or replace it."
elif [ -e "$install_root" ]; then
  [ -d "$install_root" ] || hold "$install_root exists and is not a directory; no files were changed."
  git_root=$(git -C "$install_root" rev-parse --show-toplevel 2>/dev/null) ||
    hold "$install_root is not a Git checkout; existing files were left untouched."
  expected_root=$(cd "$install_root" && pwd -P)
  [ "$git_root" = "$expected_root" ] ||
    hold "$install_root is inside a different Git checkout; existing files were left untouched."
  origin=$(git -C "$install_root" remote get-url origin 2>/dev/null) ||
    hold "The existing checkout at $install_root has no origin remote; existing files were left untouched."
  origin=${origin%/}
  case "$origin" in
    https://github.com/jkordish/orbit|https://github.com/jkordish/orbit.git|\
    git@github.com:jkordish/orbit|git@github.com:jkordish/orbit.git|\
    ssh://git@github.com/jkordish/orbit|ssh://git@github.com/jkordish/orbit.git) ;;
    *) hold "The existing checkout at $install_root is not from jkordish/orbit; existing files were left untouched." ;;
  esac
  [ -x "$install_root/scripts/sync" ] ||
    hold 'The existing Orbit checkout is incomplete; no setup was started.'
  printf 'ORBIT / INSTALLER\n  UPDATE · safely syncing the existing Orbit checkout.\n'
  "$install_root/scripts/sync"
else
  printf 'ORBIT / INSTALLER\n  CLONE · %s\n' "$install_root"
  git clone --branch main --single-branch "$repository_url" "$install_root"
fi

cd "$install_root"
[ -x ./setup ] || hold 'The Orbit checkout has no executable setup entry point.'
printf '  START · running the full repeat-safe workstation setup.\n'

if [ -t 0 ]; then
  ./setup "$@"
elif ( : </dev/tty ) 2>/dev/null; then
  ./setup "$@" </dev/tty
else
  hold 'Full setup needs a macOS Terminal session; rerun this command from Terminal.'
fi
