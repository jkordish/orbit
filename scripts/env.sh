#!/bin/bash
# shellcheck shell=bash
ORBIT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
export ORBIT_ROOT
for brew_path in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  if [ -x "$brew_path" ]; then
    eval "$("$brew_path" shellenv)"
    break
  fi
done
brew_prefix=${HOMEBREW_PREFIX:-/opt/homebrew}
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$brew_prefix/opt/rustup/bin:$brew_prefix/opt/libpq/bin:$PATH"
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_BUNDLE_NO_UPGRADE=1
