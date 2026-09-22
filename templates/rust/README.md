# {{project_name}}

A locked Rust 2024 starter using the repository's pinned stable toolchain.

## Start

```sh
cargo run --locked
```

## Check changes

```sh
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
cargo fmt --check
```

Update dependencies with Cargo and commit the resulting `Cargo.lock` change.
