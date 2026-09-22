# Verification

Run scripts/check to validate shell syntax, shell lint, tracked configuration,
and language starter projects. It does not apply Brewfiles, change macOS
preferences, start services, or contact a model provider.

Run scripts/doctor for a read-only report of installed tools and local
readiness. Doctor may inspect local package-manager state and cached Git refs.
It does not fetch, install, synchronize, or start services. On supported macOS
versions, it may read the Apple Foundation Models CLI license status; it never
accepts system-wide terms.

The full setup workflow has additional machine effects: it bootstraps Homebrew,
installs selected packages and runtimes, configures managed user settings,
applies backed-up macOS defaults, starts Apple's container service, runs a
digest-pinned container smoke check, then runs repository checks and doctor.
Review README.md and the scripts before using it on a machine.

CI runs repository checks on Linux, where macOS-only setup and service commands
are not invoked. A passing CI run verifies only the workflow steps and commit
under test; it does not verify installed tools, account state, model
availability, or macOS preferences on a user's machine.
