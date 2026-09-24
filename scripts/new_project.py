"""Create a named project from a starter template."""

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from orbit_core.report import Report, Row, render

TEMPLATES_ROOT = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_DESCRIPTIONS = {
    "python": "Python 3.13, uv, Ruff, mypy, and pytest",
    "typescript": "Node 24, pnpm, and TypeScript",
    "go": "Go with mise-managed toolchain",
    "rust": "Rust 2024 with a pinned stable toolchain",
    "nix": "optional Nix development shell",
}
GENERATED_NAMES = frozenset(
    {
        ".git",
        ".venv",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".cache",
        ".next",
        ".turbo",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "result",
        "target",
    }
)
PROJECT_NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
IDENTITY_REPLACEMENTS = {
    "python": {"python-starter": "{name}"},
    "typescript": {"typescript-starter": "{name}"},
    "go": {"example.com/go-starter": "example.com/{name}"},
    "rust": {"rust-starter": "{name}"},
    "nix": {},
}


def ignore_generated(_directory, names):
    """Exclude environment and build output even when a source tree has it."""
    return [
        name
        for name in names
        if name in GENERATED_NAMES or name.endswith((".pyc", ".pyo")) or name == ".DS_Store"
    ]


def copy_template(source, destination):
    """Copy starter files without copying local environments or build output."""
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=ignore_generated,
    )


def render_project_name(project_root, template, name):
    """Replace the starter identity in manifests, locks, and quickstart text."""
    replacements = {
        old: replacement.format(name=name)
        for old, replacement in IDENTITY_REPLACEMENTS[template].items()
    }
    replacements["{{project_name}}"] = name
    for path in project_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = content
        for old, replacement in sorted(
            replacements.items(), key=lambda item: len(item[0]), reverse=True
        ):
            updated = updated.replace(old, replacement)
        if updated != content:
            path.write_text(updated, encoding="utf-8")


def _run_git_command(staging: Path, arguments: list[str], action: str) -> None:
    """Run a Git setup step and turn failures into a useful staging error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(staging), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ValueError(f"could not {action}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        if not detail:
            detail = f"git {action} exited with status {result.returncode}"
        raise ValueError(f"could not {action}: {detail}")


def create_project(template, name, parent, initialize_git=False, initial_commit=False):
    """Create a complete project directory without overwriting existing files."""
    if template not in TEMPLATE_DESCRIPTIONS:
        available = ", ".join(TEMPLATE_DESCRIPTIONS)
        raise ValueError(f"unknown starter {template!r}; choose one of: {available}")
    if not PROJECT_NAME_PATTERN.fullmatch(name):
        raise ValueError("project name must be lowercase kebab-case and start with a letter")

    parent_path = Path(parent).expanduser()
    try:
        parent_path = parent_path.resolve(strict=True)
    except FileNotFoundError as error:
        raise ValueError(f"parent directory does not exist: {parent_path}") from error
    if not parent_path.is_dir():
        raise ValueError(f"parent path is not a directory: {parent_path}")

    destination = parent_path / name
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"destination already exists: {destination}")

    template_root = TEMPLATES_ROOT / template
    if not template_root.is_dir():
        raise ValueError(f"starter files are missing: {template_root}")
    common_root = TEMPLATES_ROOT / "common"
    for common_file in ("AGENTS.md", "gitignore"):
        if not (common_root / common_file).is_file():
            raise ValueError(f"shared starter file is missing: {common_root / common_file}")

    staging = Path(tempfile.mkdtemp(prefix=f".{name}.staging-", dir=parent_path))
    try:
        copy_template(template_root, staging)
        shutil.copy2(common_root / "AGENTS.md", staging / "AGENTS.md")
        shutil.copy2(common_root / "gitignore", staging / ".gitignore")
        render_project_name(staging, template, name)
        if initialize_git:
            _run_git_command(
                staging,
                ["init", "--initial-branch=main"],
                "initialize Git repository",
            )
            if initial_commit:
                _run_git_command(staging, ["add", "--all"], "stage the starter files")
                _run_git_command(
                    staging,
                    ["commit", "--message", "chore: initialize project"],
                    "create the initial commit",
                )
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"destination already exists: {destination}")
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def interactive_output():
    """Use visual reports only when the terminal can display them."""
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


def show_catalog():
    if not interactive_output():
        print("Available project starters:")
        for template, description in TEMPLATE_DESCRIPTIONS.items():
            print(f"  {template:<12} {description}")
        return

    render(Report(
        command="new", title="STARTERS", status="PREVIEW",
        summary=f"{len(TEMPLATE_DESCRIPTIONS)} project starters, ready to copy into an empty destination.",
        next_action="orbit new python my-app ~/src --git --commit",
        notes=["Choose an existing parent directory; existing destinations are refused.",
               "Each starter includes a README, shared AGENTS.md, and a local-data .gitignore."],
        rows=[Row("Starters", "AVAILABLE", name, description)
              for name, description in TEMPLATE_DESCRIPTIONS.items()],
    ))


def show_created(args, destination):
    project_path = shlex.quote(str(destination))
    if not interactive_output():
        print("ORBIT / NEW PROJECT")
        print(f"  Created {args.template} project {args.name!r} at {destination}")
        print("  Read README.md and AGENTS.md; install tools and dependencies when ready.")
        if args.git:
            if args.commit:
                print("  Initialized Git on main and created the initial commit; no remote was created.")
            else:
                print("  Initialized an empty Git repository on main; no commit or remote was created.")
        else:
            print(f"  Initialize Git explicitly with: cd {project_path} "
                  "&& git init --initial-branch=main")
        return

    if args.commit:
        git_state, git_detail = "COMMITTED", "Initial commit on main; no remote created"
        next_action = f"cd {project_path} && cat README.md"
    elif args.git:
        git_state, git_detail = "INITIALIZED", "Empty main branch; no commit or remote created"
        next_action = f"cd {project_path} && git status"
    else:
        git_state, git_detail = "NOT STARTED", "Initialize explicitly when ready"
        next_action = f"cd {project_path} && git init --initial-branch=main"
    render(Report(
        command="new", title="NEW PROJECT", status="CREATED",
        summary=f"{args.name} is in place. Its dependencies have not been installed.",
        next_action=next_action,
        notes=["Read README.md and AGENTS.md before installing project dependencies.",
               "Orbit left any remote and hosting choices to you."],
        rows=[Row("Project", "CREATED", args.name, TEMPLATE_DESCRIPTIONS[args.template]),
              Row("Project", "FOUND", "Directory", str(destination)),
              Row("Git", git_state, "Local repository", git_detail)],
    ))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv and interactive_output():
        show_catalog()
        return 0
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Example: ./scripts/new-project python morning-brief ~/src --git --commit",
    )
    parser.add_argument("--list", action="store_true", help="list available starters")
    parser.add_argument(
        "--git",
        action="store_true",
        help="initialize an empty local Git repository on main",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="create an initial commit after --git initializes the repository",
    )
    parser.add_argument("template", nargs="?")
    parser.add_argument("name", nargs="?")
    parser.add_argument("parent", nargs="?")
    args = parser.parse_args(argv)

    if args.list:
        if any((args.template, args.name, args.parent, args.git, args.commit)):
            parser.error("--list cannot be combined with project or Git arguments")
        show_catalog()
        return 0

    if not all((args.template, args.name, args.parent)):
        parser.error("provide a starter, project name, and existing parent directory")
    if args.commit and not args.git:
        parser.error("--commit requires --git")

    try:
        destination = create_project(
            args.template,
            args.name,
            args.parent,
            initialize_git=args.git,
            initial_commit=args.commit,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))

    show_created(args, destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
