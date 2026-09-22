# {{project_name}}

A locked Python 3.13 starter with Ruff, mypy, and pytest.

## Start

```sh
uv sync --locked
uv run python main.py
```

## Check changes

```sh
uv run ruff check .
uv run mypy .
uv run pytest
```

Use `uv add package` or `uv add --dev package` to change dependencies, then
commit the updated `uv.lock` with the source change.
