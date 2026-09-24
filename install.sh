#!/bin/bash
set -euo pipefail

repository_url='https://github.com/jkordish/orbit.git'
install_root="${HOME:?HOME must be set}/.config/orbit"

usage() {
  cat <<'EOF'
Usage: install.sh [--resume] [--profile NAME|all]...
       install.sh --preview-ui

Clone or safely update Orbit at ~/.config/orbit, then run its full setup.
Run as your normal macOS user. Optional arguments are passed to ./setup.
--preview-ui shows sample installer states without network or machine changes.
EOF
}

interactive=0
color_reset=''
color_indigo=''
color_mint=''
color_rose=''
color_muted=''
if [ -t 1 ] && [ "${TERM:-}" != dumb ]; then interactive=1; fi
if [ "$interactive" -eq 1 ] && [ -z "${NO_COLOR+x}" ]; then
  color_reset=$'\033[0m'
  color_indigo=$'\033[38;2;180;190;254m'
  color_mint=$'\033[38;2;148;226;213m'
  color_rose=$'\033[38;2;243;139;168m'
  color_muted=$'\033[38;2;166;173;200m'
fi

terminal_columns() {
  local size width
  if size=$(stty size 2>/dev/null </dev/tty); then
    size=${size##* }
    if [ "$size" -gt 0 ] 2>/dev/null; then
      width=$size
    fi
  fi
  width=${width:-${COLUMNS:-80}}
  case "$width" in ''|*[!0-9]*) width=80 ;; esac
  if [ "$width" -lt 20 ]; then width=20; fi
  printf '%s\n' "$width"
}

installer_wrap() {
  local remaining=$1 limit=$2 chunk
  while [ "${#remaining}" -gt "$limit" ]; do
    chunk=${remaining:0:limit}
    if [[ $chunk == *' '* ]]; then chunk=${chunk% *}; fi
    if [ -z "$chunk" ]; then chunk=${remaining:0:limit}; fi
    printf '  %s\n' "$chunk"
    remaining=${remaining:${#chunk}}
    while [[ $remaining == ' '* ]]; do remaining=${remaining# }; done
  done
  printf '  %s\n' "$remaining"
}

installer_intro() {
  local width
  if [ "$interactive" -eq 0 ]; then
    printf 'ORBIT / INSTALL\n  Checkout, then workstation setup\n'
    return
  fi
  width=$(terminal_columns)
  printf '\n  %s◉ ORBIT / INSTALL%s\n' "$color_indigo" "$color_reset"
  if [ "$width" -lt 42 ]; then
    printf '  %sCheckout → setup%s\n' "$color_muted" "$color_reset"
  else
    printf '  %sCheckout, then workstation setup%s\n' "$color_muted" "$color_reset"
  fi
}

installer_stage() {
  local number=$1 label=$2 detail=$3 short_detail=$4 width
  if [ "$interactive" -eq 0 ]; then
    printf '\n  %02d/02 · %s · %s\n' "$number" "$label" "$detail"
    return
  fi
  width=$(terminal_columns)
  printf '\n  %s%02d/02%s  %s\n' "$color_indigo" "$number" "$color_reset" "$label"
  if [ "$width" -lt 42 ]; then
    printf '  %s%s%s\n' "$color_muted" "$short_detail" "$color_reset"
  else
    printf '    %s%s%s\n' "$color_muted" "$detail" "$color_reset"
  fi
}

installer_ready() {
  if [ "$interactive" -eq 1 ]; then
    printf '  %s✓%s  Checkout ready\n' "$color_mint" "$color_reset"
  else
    printf '  DONE · Checkout ready\n'
  fi
}

installer_hold() {
  local reason=$1 width
  if [ "$interactive" -eq 0 ]; then
    printf '\nORBIT / HOLD\n  %s\n' "$reason"
    return
  fi
  width=$(terminal_columns)
  case "$width" in ''|*[!0-9]*) width=80 ;; esac
  if [ "$width" -lt 20 ]; then width=20; fi
  printf '\n  %s◉ ORBIT / HOLD%s\n' "$color_rose" "$color_reset"
  installer_wrap "$reason" "$((width - 2))"
}

hold() {
  installer_hold "$1" >&2
  exit 1
}

installer_sample_label() {
  if [ "$interactive" -eq 1 ]; then
    printf '\n  %s%s%s' "$color_muted" "$1" "$color_reset"
  else
    printf '\n%s' "$1"
  fi
}

installer_preview() {
  if [ "$interactive" -eq 1 ]; then
    printf '\n  %s◉ ORBIT / APPEARANCE%s\n' "$color_indigo" "$color_reset"
    printf '  %sRead-only installer samples%s\n' "$color_muted" "$color_reset"
  else
    printf 'ORBIT / APPEARANCE\n  Read-only installer samples\n\n'
  fi
  installer_intro
  installer_sample_label 'FRESH CHECKOUT'
  installer_stage 1 'Checkout' 'Cloning to ~/.config/orbit' 'Cloning Orbit'
  installer_ready
  installer_sample_label 'EXISTING CHECKOUT'
  installer_stage 1 'Checkout' 'Safely syncing an existing Orbit checkout' 'Syncing main'
  installer_ready
  installer_sample_label 'HANDOFF'
  installer_stage 2 'Workstation' 'Seven setup phases follow' 'Setup follows'
  installer_sample_label 'IF BLOCKED'
  installer_hold 'Finish the Command Line Tools installer, then rerun the curl command.'
}

if [ "${1:-}" = --help ]; then
  usage
  exit 0
fi
if [ "$#" -eq 1 ] && [ "$1" = --preview-ui ]; then
  installer_preview
  exit 0
fi
for argument in "$@"; do
  if [ "$argument" = --preview-ui ]; then
    printf 'Usage: install.sh --preview-ui (without other options)\n' >&2
    exit 2
  fi
done

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  hold 'This installer targets Apple Silicon macOS.'
fi
if [ "$(id -u)" -eq 0 ]; then
  hold 'Do not run as root or with sudo; use your normal account.'
fi
if [ ! -t 0 ] && ! ( : </dev/tty ) 2>/dev/null; then
  hold 'Full setup needs a macOS Terminal session; rerun this command from Terminal.'
fi

if ! xcode-select -p >/dev/null 2>&1; then
  xcode-select --install || true
  hold 'Finish the Apple Command Line Tools installer, then rerun the curl command.'
fi
command -v git >/dev/null 2>&1 || hold 'Git is unavailable; install Apple Command Line Tools and retry.'

installer_intro
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
  installer_stage 1 'Checkout' 'Safely syncing an existing Orbit checkout' 'Syncing main'
  ORBIT_INSTALL_CONTEXT=installer "$install_root/scripts/sync"
else
  installer_stage 1 'Checkout' 'Cloning to ~/.config/orbit' 'Cloning Orbit'
  if ! git clone --branch main --single-branch "$repository_url" "$install_root"; then
    hold 'Clone failed. Check GitHub access and review any partial checkout before retrying.'
  fi
fi

cd "$install_root"
[ -x ./setup ] || hold 'The Orbit checkout has no executable setup entry point.'
installer_ready
installer_stage 2 'Workstation' 'Seven setup phases follow' 'Setup follows'

if [ -t 0 ]; then
  ./setup "$@"
elif ( : </dev/tty ) 2>/dev/null; then
  ./setup "$@" </dev/tty
else
  hold 'Full setup needs a macOS Terminal session; rerun this command from Terminal.'
fi
