# Repository guidance

## Purpose and boundaries

This repository provisions a general Apple Silicon macOS developer workstation.
Keep defaults project-agnostic; do not add application-specific project setup.
Read README.md for user instructions and docs/verification.md for verification
scope.

## Preserve machine state

- Treat .state/, its backups, installed environments, and ignored files as
  local user data. Never clear them during routine development.
- Do not use git clean, hard resets, forced checkouts, or remove branches or
  worktrees to make a checkout look tidy. Preserve existing work.
- Use ./scripts/sync to return the primary checkout to main. It fast-forwards
  only, refuses unsafe states, and never publishes commits.
- ./scripts/recovery is observational: it reports backup names, sizes, and
  filename-based destination hints but never reads contents, restores, or
  removes anything. Treat ambiguous or unknown targets as manual-review items.

## Tool ownership

- Homebrew owns macOS applications and system packages listed in Brewfiles.
- mise owns the pinned Node.js, Go, and pnpm versions; uv owns Python
  environments; rustup owns the stable Rust toolchain.
- Project dependencies stay owned by each project and its lockfiles.
- Preserve lockfiles and pinned versions. Update related manifests and locks
  together when a version change is part of the task.

## Command effects

- scripts/doctor checks readiness without installing, synchronizing, or
  starting tools.
- scripts/services starts or inspects container services; stop actions check
  for active workloads and do not delete user data.
- scripts/apply installs and configures packages, runtimes, editor extensions,
  and selected profiles.
- setup runs the full provisioning flow, including macOS defaults and a
  pinned container smoke check. Its state directory, lock, and phase record
  must be real paths rather than symbolic links before any setup write.
- scripts/check validates shell, configuration, Python, TypeScript, Go, and
  Rust without applying workstation Brewfiles or starting services.
- scripts/projects only inventories project manifest filenames under the
  selected source directory; it does not open manifests or execute project code.
  Symbolic-link child directories are skipped and disclosed.
- orbit profiles displays optional Brewfiles and selected names without
  installing packages or changing selection. Piped scripts/profiles --list
  output keeps its existing format. Keep profile descriptions aligned with
  their Brewfiles.
- orbit plan inventories simple base and selected profile Brewfile declarations
  without evaluating Ruby or probing Homebrew. Reads are bounded to 128 KiB
  per manifest. Counts are declarations, not missing packages. Unrecognized or
  conditional rules must stay visible for review rather than being presented
  as resolved installs. macOS preferences that differ or cannot be read stay
  visible; matching values may be summarized by default and expanded with
  `--details` in both text and JSON.
- scripts/orbit map reuses bounded project entry checks for immediate children
  of one source directory. It skips symbolic links, reports incomplete scan
  coverage, and does not run project code or change project files.
- orbit map --needs summarizes recognized project stacks and aggregates only
  valid, explicit .orbit.json profile requests from inspected projects. It
  suggests one read-only plan for missing selections without inferring optional
  profiles from language manifests. With --git, dirty, ahead, and divergent Git
  state keeps next-action priority.
- orbit map --git compares project checkouts only with their cached configured
  upstreams. Never fetch, sync, or publish from this view; preserve local work
  and avoid assuming every project uses main.
- orbit repo inspects one checkout with cached refs and read-only Git options
  that avoid index refresh. Recommend Orbit's sync command only for the Orbit
  checkout; other repositories must use their own Git workflow.
- scripts/enter reads bounded project declarations and probes local tools;
  it never executes project code or changes project or machine state.
- orbit new without arguments opens a starter catalog on interactive terminals.
  Creating a project retains the plain piped output contract and never
  overwrites an existing destination or creates a remote.
- scripts/orbit_core owns read-only status, plan, projects, enter, and map report building.
  Keep its text and JSON results aligned, avoid project code execution, and
  preserve exit codes. The Bash installer/setup and recovery paths must work
  before Orbit's managed Python exists.

## Presentation review

- Review every user-facing terminal change at wide and narrow widths, with
  `NO_COLOR`, and with piped or `TERM=dumb` output. Inspect success, failure,
  and empty or skipped states where they exist.
- Keep the current state and one useful next action easy to find. Color is
  supplemental; words and symbols must still carry meaning without it.
- Avoid repeated banners in the full setup flow. Preserve underlying command
  output so a failed phase remains diagnosable. Use `./setup --preview-ui` to
  review real setup renderers without provisioning or writing `.state`.

## Shared AI guidance

Keep shared AGENTS.md, CLAUDE.md, and editor instructions trackable. Local
assistant sessions and generated notes are intentionally ignored, including
.codex/, .claude/, .superpowers/, and docs/superpowers/. Never add those local
artifacts to commits. templates/common/AGENTS.md is copied into new starter
projects; keep it aligned with the starter workflow when changing it.
