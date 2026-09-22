# {{project_name}}

A locked Go starter managed with mise.

## Start

Review `mise.toml`, then trust and install its pinned Go toolchain:

```sh
mise trust
mise install --locked
go run .
```

## Check changes

```sh
go test ./...
go vet ./...
```

The initial module path is `example.com/{{project_name}}`. Change it to your
published module path before adding imports that refer to this module.
