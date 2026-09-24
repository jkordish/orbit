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

## Change preview

`orbit plan` is a read-only first step toward an inspectable setup. It resolves
the same profile names as apply and uses the configurator's file comparison
logic to preview creates and changes. It displays destinations and backup
intent, never file contents. The current plan does not cover package resolution,
runtime installation, macOS defaults, or services, so setup remains the owner
of those effects. Future receipts and restoration should reuse this change
model and refuse to overwrite a destination that changed after Orbit applied it.

## Project entry

`orbit enter` is a read-only bridge between general workstation provisioning
and a project's own setup. A bounded manifest scan identifies likely language
toolchains. Small, explicit version declarations are compared with local tools;
unparsed ranges remain review items. A root `.orbit.json` can request only
known Orbit profiles and container services. Orbit never runs project hooks,
installs project dependencies, or changes a project checkout during entry.
`orbit map` reuses that inspection to summarize immediate child projects under
one source directory. It shows an empty Git checkout as a review item, limits
the scan to 128 child directories, reports incomplete coverage, and directs the
user to `orbit enter` for detail. The existing `orbit projects` command remains
a manifest-filename inventory that does not open project declarations.
The optional `orbit map --git` view adds a separate Git snapshot for each
recognized project. It checks the working tree and configured upstream using
cached refs, never network or Orbit's main-only synchronization policy. Dirty,
ahead, and diverged projects receive priority in the suggested next action;
the view offers a read-only Git status command for manual inspection.

## Command architecture

`install.sh`, `bootstrap.command`, `setup`, and package actions remain Bash
entrypoints. They can run before Orbit's managed Python is installed and retain
their serialized, backup-aware setup behavior. `scripts/orbit` remains the
single command front door. Its read-only `status`, `plan`, `enter`, and `map` commands
use `scripts/orbit_core/`, a Python standard-library package compatible with
the Command Line Tools Python. The Bash wrappers select that interpreter and
disable bytecode writes. Recovery inventory and Git synchronization remain
separate Bash commands with their established safety contracts.

The core builds a structured report first, then renders text or schema-versioned
JSON. Each row has a group, state, label, and detail. Exit codes retain their
meaning: 0 for ready or a successful preview, 1 for action needed or a failed
check, and 2 for invalid input. JSON is an output view of the same checks; it
does not trigger setup, service changes, or project code.
