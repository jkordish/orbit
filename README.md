# Orbit

A repeatable, reversible setup for an Apple Silicon macOS development machine.
It provides general tooling for Rust, TypeScript, Python, Go, containers,
shell work, and editor workflows. It does not configure any application or
project checkout.

## Quick start

Review the package lists and scripts before applying them. On a fresh Mac:

    git clone <repository-url> ~/.config/orbit
    cd ~/.config/orbit
    ./setup

Setup bootstraps Homebrew when needed, installs declared base packages,
applies profiles you explicitly select, installs language runtimes from checked
manifests, configures managed shell/editor preferences, starts Apple's
container service, runs a digest-pinned container smoke check, and reports
readiness. It needs network access and several GB of free space. Homebrew's
initial installation may ask for your administrator password; run the rest as
your normal user. Do not run setup with sudo.

This is a real workstation change. Review Brewfile, profiles/, scripts/apply,
scripts/configure.py, and scripts/macos-defaults first. Setup is safe to rerun:
package installation does not upgrade or remove existing packages, managed
configuration is backed up before replacement, unchanged configuration does
not create repeat backups, and setup phases are serialized. Local state and
backups live under ignored .state/.

If a run stops, inspect .state/provision-state and resume with:

    ./setup --resume

A normal ./setup reconciles from the beginning. For a read-only readiness
report, run ./scripts/doctor. To install packages and configure dotfiles
without the full service and smoke-check phases, use ./scripts/apply.

## Commands

| Command | Purpose |
| --- | --- |
| ./setup | Full repeatable workstation provisioning |
| ./scripts/apply | Install packages, runtimes, profiles, and managed configuration |
| ./scripts/doctor | Read-only readiness report |
| ./scripts/check | Repository and language-template validation |
| ./scripts/profiles --list | Show optional profiles |
| ./scripts/services status | Inspect container service state |
| ./scripts/services | Start Apple's container service |
| ./scripts/container-check | Run the pinned container smoke check |
| ./scripts/docker-start | Start the optional Colima Docker-compatible VM |
| ./scripts/projects | Inventory language manifests under ~/src without running project code |
| ./scripts/recovery | Inspect preserved setup backups without reading their contents |
| ./scripts/sync | Safely fast-forward a clean checkout to main |
| ./scripts/new-project | Create a starter project from a language template |
| ./scripts/update | Explicitly update managed packages and dependencies |

Doctor checks local state and installed tools. It does not install, fetch,
synchronize, or start services. On macOS versions that include Apple's
Foundation Models CLI, doctor may report whether its system-wide license terms
have been accepted. It never agrees to terms; that decision belongs to the
machine's administrator.

## Profiles

Base installation provides common developer utilities and Rust, Node.js, Go,
Python, and pnpm. Additional Brewfile profiles are opt-in. Selected profile
names are stored in ignored .state/profiles.txt, not tracked configuration.

    ./setup --profile editors
    ./setup --profile infra --profile cloud
    ./scripts/profiles --list

Available profiles are autocomplete, cloud, editors, infra, java, and wasm. The
cloud profile currently provides AWS tooling. Review each profile Brewfile
before selecting it; Homebrew taps and formulas run third-party installation
code.

## Runtime and package ownership

- Homebrew owns macOS applications and system packages in the Brewfiles.
- mise owns the pinned Node.js, Go, and pnpm versions.
- uv owns the pinned Python version and locked virtual environments.
- rustup owns Rust; Rust commands use the stable toolchain.
- Each project owns its dependencies and lockfiles.

Package manager versions and macOS can change over time. Runtime locks pin
project tool versions and dependencies; Homebrew applications, system packages,
SDKs, and container VM images are rolling components.

To update managed dependencies intentionally, start from a clean Git checkout:

    ./scripts/update

This upgrades selected Homebrew bundles and locked language dependencies, then
runs repository checks. Review resulting lockfile changes before committing.
The command does not change the Rust channel from stable.

## Shell and configuration

Setup manages Zsh, Git, SSH, Starship, Ghostty, Docker CLI plugin paths, and
selected macOS preferences. Existing configuration is preserved through include
files where practical; changed files are backed up under .state/backups/.
Git identity and private keys are not supplied here. Set your own user.name and
user.email; SSH keys remain in your existing agent or ~/.ssh.

The included SSH defaults apply only to github.com. Existing HTTPS remotes
continue to work. Shell startup is added once to ~/.zshrc, and macOS preference
changes are backed up before application. Reopen affected apps or start a new
terminal to observe those changes.

The services disable/sleep commands stop only idle services. They refuse to
stop containers with running workloads. Stopping a service does not delete
images, volumes, or other user data. Colima is opt-in and is not started by
normal setup.

## Starter projects

The starter command creates Python, TypeScript, Rust, Go, or Nix projects. It
copies no caches, virtual environments, or build output. New projects include
shared AGENTS.md guidance and a .gitignore that excludes local assistant
sessions and generated notes while leaving shared instructions trackable.

    mkdir -p ~/src
    ./scripts/new-project --list
    ./scripts/new-project python example ~/src --git --commit

The templates use lockfiles and document their checks. The Nix template asks
you to create and commit flake.lock for a specific project before sharing it.

## AI tooling and local data

This repository does not select a model provider, download model weights, send
prompts, or configure a particular coding assistant. Install and configure
assistant applications separately. Repository and starter .gitignore files
exclude local assistant sessions and generated notes, including .codex/,
.claude/, .superpowers/, and docs/superpowers/, while shared AGENTS.md,
CLAUDE.md, and editor instructions remain trackable.

Apple's fm command is independent of setup. If it is available, doctor only
reports its license status. It never runs sudo fm license or accepts
system-wide terms.

## Repository checks

GitHub Actions scans the public repository history for secrets and runs
scripts/check on pull requests and changes to main. CI validates shell,
configuration, and language templates without applying workstation Brewfiles
or starting services.

    ./scripts/check
