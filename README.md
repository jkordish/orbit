<p align="center">
  <img src="assets/orbit-mark.svg" width="112" height="112" alt="Orbit mark: a mint satellite circling a central star">
</p>

<h1 align="center">Orbit</h1>

<p align="center"><strong>A calm, capable Mac in one repeatable setup.</strong><br>
General development tooling for Apple Silicon macOS, with previews, preserved
configuration backups, and clear next steps.</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#safety-and-recovery">Safety and recovery</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#profiles">Profiles</a>
</p>

<p align="center">
  <a href="https://github.com/jkordish/orbit/actions/workflows/checks.yml"><img src="https://github.com/jkordish/orbit/actions/workflows/checks.yml/badge.svg" alt="Repository checks"></a>
</p>

| See the state | Set up the machine | Keep a way back |
| --- | --- | --- |
| `orbit status`, `profiles`, `plan`, `enter`, and `map` explain choices and readiness before changes. | `orbit provision` installs general Rust, TypeScript, Python, Go, container, shell, and editor tooling. | Managed files are backed up before replacement; `orbit recovery` inventories saved backups. |

Orbit does not configure any application or project checkout.
After setup, the managed Zsh configuration provides `orbit` as a shell command;
before setup, use `./scripts/orbit` from the checkout.

## Quick start

Review the package lists and scripts before applying them. For a fresh Mac,
download and run the current `main` installer with:

    curl --fail --location --proto '=https' --tlsv1.2 \
      https://raw.githubusercontent.com/jkordish/orbit/main/install.sh | /bin/bash

The installer checks for Apple Silicon macOS and Command Line Tools, clones
Orbit into `~/.config/orbit`, and runs the complete setup. It reuses and safely
syncs an existing Orbit checkout; it refuses to replace a different directory,
repository, or symbolic link. Review [install.sh](install.sh) first if you want
to inspect the bootstrap code. Optional profiles can be selected in the same
command. Use `all` to include every optional profile currently defined in
`profiles/`:

    curl --fail --location --proto '=https' --tlsv1.2 \
      https://raw.githubusercontent.com/jkordish/orbit/main/install.sh | /bin/bash -s -- --profile all

To inspect a checkout before changing the machine, clone Orbit and preview the
selected profile and managed-file changes:

    git clone https://github.com/jkordish/orbit.git ~/.config/orbit
    cd ~/.config/orbit
    ./scripts/orbit plan
    ./scripts/orbit status

When ready, run setup from that checkout. Add `--profile all` to both `plan`
and `setup` if you want every optional profile:

    ./setup

Setup bootstraps Homebrew when needed, installs declared base packages,
applies profiles you explicitly select, installs language runtimes from checked
manifests, configures managed shell/editor preferences, starts Apple's
container service, runs a digest-pinned container smoke check, and reports
readiness. It needs network access and several GB of free space. Homebrew's
initial installation may ask for your administrator password; run the rest as
your normal user. Do not run setup with sudo. Interactive setup shows all seven
phases and the current step; piped logs keep plain phase labels.

## Safety and recovery

This is a real workstation change. Review Brewfile, profiles/, scripts/apply,
scripts/configure.py, and scripts/macos-defaults first. Setup is safe to rerun:
Homebrew is asked to avoid upgrades and package removal, managed configuration
is backed up before replacement, unchanged configuration does not create repeat
backups, and setup phases are serialized. Homebrew may still upgrade a package
when [installation requires it](https://docs.brew.sh/Manpage). Local state and
backups live under ignored .state/; scripts/recovery inventories them for
manual restoration. Its interactive view summarizes saved items and highlights
ambiguous or unknown destinations before the full list, without opening backup
contents.

If a run stops, inspect .state/provision-state and resume with:

    ./setup --resume

To select new profiles, run a normal `./setup --profile NAME` so apply is not
skipped. `--resume` rejects profile arguments.

A normal ./setup reconciles from the beginning. For a read-only readiness
report, run ./scripts/doctor. To install packages and configure dotfiles
without the full service and smoke-check phases, use ./scripts/apply.

The `./scripts/orbit` command groups the day-to-day views and explicit actions.
Run it without arguments for an interactive command board that adapts to narrow
terminals and points to the first useful commands. Piped help and `TERM=dumb`
keep the plain text layout; `NO_COLOR` removes terminal color.
Its read-only `status`, `plan`, `projects`, `enter`, and `map` views share a
Python core and support `--json` for scripts and integrations:

    ./scripts/orbit status --json
    ./scripts/orbit plan --profile wasm --json
    ./scripts/orbit enter ~/src/example --json
    ./scripts/orbit projects --json
    ./scripts/orbit map ~/src --json
    ./scripts/orbit map ~/src --git --json

JSON reports use schema version 1 and contain a status, rows, a next action,
and an exit code matching the command result. The core uses only the Python
standard library and runs without creating a virtual environment. The curl
installer and initial provisioning remain Bash so they can bootstrap Python.
On an interactive terminal, these views use a compact, responsive layout with
status colors and a clear next step. `NO_COLOR` removes color, and `TERM=dumb`
or piped output uses stable plain text. `--json` always emits the same data
regardless of terminal settings.

## Commands

| Command | Purpose |
| --- | --- |
| ./scripts/orbit | Unified command center for views and explicit actions |
| ./setup | Full repeatable workstation provisioning |
| ./scripts/apply | Install packages, runtimes, profiles, and managed configuration |
| ./scripts/doctor | Read-only readiness report |
| ./scripts/plan | Read-only preview of profile selection and managed file changes |
| ./scripts/enter [path] | Read-only project tool readiness view |
| ./scripts/orbit map [source-directory] | Read-only readiness map of immediate child projects |
| ./scripts/orbit repo [path] | Read-only main/origin/main state for one checkout |
| ./scripts/check | Repository and language-template validation |
| ./scripts/orbit profiles | Show optional profiles and selected choices |
| ./scripts/services status | Inspect container service state |
| ./scripts/services | Start Apple's container service |
| ./scripts/container-check | Run the pinned container smoke check |
| ./scripts/docker-start | Start the optional Colima Docker-compatible VM |
| ./scripts/orbit projects [--json] | Inventory language manifest filenames under ~/src without running project code |
| ./scripts/recovery | Inspect preserved setup backups without reading their contents |
| ./scripts/sync | Safely fast-forward a clean checkout to main |
| ./scripts/new-project | Create a starter project from a language template |
| ./scripts/update | Explicitly update managed packages and dependencies |

Doctor checks local state and installed tools. It does not install, fetch,
synchronize, or start services. On macOS versions that include Apple's
Foundation Models CLI, doctor may report whether its system-wide license terms
have been accepted. It never agrees to terms; that decision belongs to the
machine's administrator.

From a checkout, preview optional profile selection and managed user file edits
before applying:

    ./scripts/plan --profile all
    ./setup --profile all

The preview lists target paths and whether an existing file would be backed up;
it never prints file contents. Its current scope is profile choices and managed
user files. Full setup also installs packages and runtimes, applies macOS
preferences, starts services, and runs checks.

To check a project before opening it, run `./scripts/orbit enter ~/src/example`
or `./scripts/enter` from inside that project. Enter inspects standard manifest
filenames through two directory levels, compares declared versions with the
active local toolchains where it can, and gives one next action. It does not
run project scripts, install dependencies, start services, or write files. A
tooling-ready result means only that checked tools and requested services are
available and requested profiles are selected; project builds and dependencies
still belong to that project. Unsupported version ranges and scan limits are
reported for review instead of being marked ready.

Projects may declare optional Orbit requirements in a small `.orbit.json` at
their root:

    {"version":1,"profiles":["wasm"],"services":["container"]}

Only existing Orbit profiles and the `container` or `docker` services are
accepted. This file declares requirements; it cannot run hooks or commands.
Enter exits 0 for tooling ready, 1 for action or review, and 2 for invalid
input. It reads bounded manifest files to extract version declarations and the
optional requirements file; it never prints their contents.

To see your source workspace at a glance, run `./scripts/orbit map`. It uses
`~/src` by default, or `DEV_MACHINE_SRC_ROOT` / `ORBIT_SRC_ROOT` when set. The
map checks immediate child directories with a Git checkout or recognized
manifest, reuses `enter`'s bounded checks, and shows `READY`, `ACTION`, or
`REVIEW` for each project. An empty Git checkout is shown as `REVIEW`. The first
project needing attention becomes the next `orbit enter` command. The map
skips symbolic links, scans at most 128 child directories, reports any omitted
directories, and does not run project code or change a checkout. Its result is
tool readiness, not a project build or dependency check. `orbit projects`
remains a fast manifest-filename inventory. It counts detected language families
without opening manifests and supports the same interactive, plain, and JSON
report views as the readiness commands.

Add `--git` to the map for a local Git safety view across those projects:

    ./scripts/orbit map --git

It reports local changes, branch and configured upstream, and ahead/behind
counts without printing changed filenames. Comparisons use cached upstream
refs; Orbit never fetches, syncs, commits, or publishes from this view. A
`MATCH` row means only that the local commit matches the cached upstream ref.
Local changes and unpushed commits take priority in the suggested next action.
Worktrees with a `.git` file are supported; symbolic-link Git markers are
reported for review without being followed.

## Profiles

Base installation provides common developer utilities and Rust, Node.js, Go,
Python, and pnpm. Additional Brewfile profiles are opt-in. Selected profile
names are stored in ignored .state/profiles.txt, not tracked configuration.

    ./setup --profile editors
    ./setup --profile infra --profile cloud
    ./scripts/orbit profiles

Available profiles are autocomplete, cloud, editors, infra, java, and wasm.
`--profile all` selects every optional profile defined in `profiles/`. The
cloud profile currently provides AWS tooling. Review each profile Brewfile
before selecting it; Homebrew taps and formulas run third-party installation
code. The interactive catalog shows selection, not installed-package readiness.

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
