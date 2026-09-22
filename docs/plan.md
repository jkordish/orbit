# Orbit workstation design

Orbit is a general workstation bootstrap for Apple Silicon macOS. It owns
system packages, shared shell/editor configuration, and pinned language
toolchains. It does not own application checkouts, their dependencies, local AI
models, or account credentials.

## Ownership

- Homebrew installs macOS applications and system packages from the base and
  explicitly selected profile Brewfiles.
- mise installs pinned Node.js, Go, and pnpm versions.
- uv installs Python and creates locked environments for the templates.
- rustup installs stable Rust and its standard components.
- Individual projects own their language manifests, secrets, services, and
  build/test workflows.

## Provisioning boundaries

Setup is explicit and repeat-safe. It refuses root and unsupported hosts,
serializes concurrent runs, preserves generated environments on relocation,
backs up changed user configuration, and never applies a hosted model or
project-specific integration. GitHub Actions validates repository contents
without running workstation setup.

Local profiles and recovery backups belong under ignored .state/. Shared
instructions and templates remain versioned. Never commit credentials, local
assistant sessions, machine inventories, or generated setup history.
