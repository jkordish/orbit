# Verification

Run scripts/check to validate shell syntax, shell lint, tracked configuration,
and language starter projects. It does not apply Brewfiles, change macOS
preferences, start services, or contact a model provider.

Run scripts/doctor for a read-only report of installed tools and local
readiness. Doctor may inspect local package-manager state and cached Git refs.
It does not fetch, install, synchronize, or start services. On supported macOS
versions, it may read the Apple Foundation Models CLI license status; it never
accepts system-wide terms.

Run scripts/plan with optional `--profile` choices for a read-only preview of
profile selection, managed user file changes, and macOS preferences. It reports
paths and backup intent without displaying file contents or creating state.
On macOS it compares the declared preference types and values with in-memory
domain exports, showing differing keys without printing existing
values. An unreadable domain is marked for review. Its static Brewfile
inventory counts declared formulae, casks, and taps for the base and selected
profiles and flags conditional or unparsed lines. It does not run Brewfile
Ruby, ask Homebrew what is installed, or resolve package actions. Runtime
installation and service effects remain outside this scope.

Run `scripts/enter [project directory]` for a bounded, read-only project
tooling check. It scans standard manifest names, reads only small version
declarations and an optional `.orbit.json`, then probes local tool commands and
requested service status. It never executes project code or installs anything.
The result does not establish dependency, build, test, or application health.
Selected profiles are checked by name; their packages are not verified here.

The read-only `status`, `plan`, `projects`, `enter`, and `map` views use the
standard-library Python core. `--json` returns the same report as text with
`schema_version: 1`, including exit code and next action. The wrappers disable
Python bytecode writes. `scripts/check` exercises text/JSON rendering,
interactive layout, narrow terminal wrapping, invalid arguments, profile
previews in an isolated home, project entry, and doctor check results with
local probes stubbed. Package names and paths wrap at separators when possible.
The real doctor can still report missing installed tools after repository
checks pass; no installer is run by those checks.
`orbit projects` checks immediate child manifest filenames only. It skips
symbolic-link child directories, reports their count, and never reads project
declarations. Its JSON output is an inventory, not a tooling verdict.
The Bash command board is a presentation-only view: run `scripts/orbit` in an
interactive terminal for its compact layout, or pipe `scripts/orbit help` for
plain text. Neither path runs readiness probes or changes machine state.
`scripts/orbit repo [path]` presents a wrapped status card in an interactive
terminal. Piped output and `TERM=dumb` retain the three-field TSV format.
It compares the checkout against main and cached origin/main. For another
checkout, its next action refers to that checkout's Git workflow;
Orbit's `scripts/sync` is recommended only for Orbit itself. This command
inspects local state and cached `origin/main` without fetching or syncing.
`scripts/recovery` shows a responsive summary, review-first names, and wrapped
filename-based hints on interactive terminals. Piped output and `TERM=dumb`
retain the existing line-oriented inventory. Counts come from entry types and
filenames, never backup contents; unknown and ambiguous targets remain
manual-review items.
`orbit profiles` shows selected optional profiles and Brewfile-based
descriptions without installing packages. The interactive catalog does not
establish package readiness; piped `scripts/profiles --list` retains its plain
format for scripts.
`orbit new` shows the starter catalog on an interactive terminal; `--list`
does the same explicitly. Starter creation uses the shared visual report for
interactive receipts, with directory, local Git state, and next action.
Piped starter output keeps its previous format, and `orbit new` without
arguments still reports usage when piped. No catalog view creates a project.
The map check covers mixed readiness, invalid declarations, manifest-free Git
checkouts, symbolic-link exclusion, scan-limit disclosure, and unchanged
project files. A ready row confirms only the checks described by `orbit enter`.
The optional `--git` check is verified in isolated repositories for matching,
dirty, ahead, behind, diverged, worktree, and symbolic-link states. It uses
cached refs and disables Git optional locks, lazy fetches, and file-system monitors; the
focused check confirms the index bytes and modification time stay unchanged.
It does not establish current remote state because it never fetches.
The optional `map --needs` view reuses `enter`'s bounded stack scan and
validated `.orbit.json` profile rows. It reports selected names and deduplicates
unselected names into a read-only `orbit plan` command; it does not infer
optional profiles from language manifests or verify installed profile packages.
Scan coverage warnings and Git priority remain in effect.

The full setup workflow has additional machine effects: it bootstraps Homebrew,
installs selected packages and runtimes, configures managed user settings,
applies backed-up macOS defaults, starts Apple's container service, runs a
digest-pinned container smoke check, then runs repository checks and doctor.
Review README.md and the scripts before using it on a machine. The interactive
setup phase cards do not change phase state or resume ordering. Setup refuses
symbolic links for its state directory, lock, and phase record before writing.

CI runs repository checks on Linux, where macOS-only setup and service commands
are not invoked. A passing CI run verifies only the workflow steps and commit
under test; it does not verify installed tools, account state, model
availability, or macOS preferences on a user's machine.
