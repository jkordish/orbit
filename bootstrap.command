#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo 'This bootstrap targets Apple Silicon macOS.' >&2
  exit 1
fi
if ! xcode-select -p >/dev/null 2>&1; then
  xcode-select --install
  if [ "${ORBIT_SETUP_CONTEXT:-}" = full ]; then
    echo 'Finish the Apple Command Line Tools installer before resuming setup.'
  else
    echo 'Finish the Apple Command Line Tools installer, then run this file again.'
  fi
  exit 1
fi
if [ ! -x /opt/homebrew/bin/brew ]; then
  installer=$(mktemp -t orbit-homebrew)
  trap 'rm -f "$installer"' EXIT
  curl --fail --location --proto '=https' --tlsv1.2 \
    https://raw.githubusercontent.com/Homebrew/install/641127e1d6a9b5fd01dd4582abe174b7a4069bba/install.sh \
    -o "$installer"
  actual=$(shasum -a 256 "$installer" | awk '{print $1}')
  [ "$actual" = 12479a24be3f5307eecac7cde670fad7118640f031229e964f544b1367b52a41 ] || { echo 'Installer checksum mismatch' >&2; exit 1; }
  /bin/bash "$installer"
fi
if [ "${ORBIT_SETUP_CONTEXT:-}" != full ]; then
  echo 'Homebrew is ready. Run ./scripts/apply from this directory to apply the setup.'
fi
