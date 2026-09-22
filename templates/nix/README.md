# {{project_name}}

An optional Nix development shell for native build tools on Apple Silicon macOS
and Linux. This starter does not install Nix or generate a lockfile for you.

## Start

Review `flake.nix` and `.envrc` first. Install Nix using your preferred method,
then pin the input and enter the shell:

```sh
nix flake lock
nix develop
```

Commit `flake.lock` so collaborators use the same nixpkgs revision. If you use
direnv, review `.envrc` before running `direnv allow`.
