# {{project_name}}

A locked Node 24 and TypeScript starter managed with mise and pnpm.

## Start

Review `mise.toml`, then trust and install its pinned tools before running them:

```sh
mise trust
mise install --locked
pnpm install --frozen-lockfile
pnpm start
```

## Check changes

```sh
pnpm check
pnpm test
```

Use pnpm to change dependencies and commit the updated lockfile with the source
change.
