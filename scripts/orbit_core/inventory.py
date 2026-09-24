"""Fast, filename-only inventory of projects below a source directory."""

from __future__ import annotations

from pathlib import Path

from .report import Report, Row


def _languages(project: Path) -> list[str]:
    """Inspect manifest names without opening project files."""
    found: list[str] = []
    if (project / "Cargo.toml").is_file():
        found.append("Rust")
    if (project / "go.mod").is_file():
        found.append("Go")
    if (project / "pyproject.toml").is_file() or (project / "requirements.txt").is_file():
        found.append("Python")
    if (project / "package.json").is_file() or (project / "pnpm-workspace.yaml").is_file():
        found.append("JavaScript/TypeScript")
    if ((project / "Package.swift").is_file()
            or any(project.glob("*.xcodeproj/project.pbxproj"))
            or any(project.glob("*.xcworkspace/contents.xcworkspacedata"))):
        found.append("Apple")
    if (project / "flake.nix").is_file():
        found.append("Nix")
    return found


def build_report(source: Path) -> Report:
    """Inventory every immediate child directory; never read manifest contents."""
    notes = [f"Source root: {source}",
             "Manifest filenames only; project code and configuration are not opened.",
             "Immediate child directories only; symbolic links are skipped."]
    if not source.is_dir():
        return Report(
            command="projects", title="PROJECT INVENTORY", status="EMPTY",
            summary="No source directory found.",
            next_action=f"Create {source} or set DEV_MACHINE_SRC_ROOT to an existing source directory.",
            notes=notes, rows=[Row("Projects", "EMPTY", "No source directory", str(source))],
        )

    projects: list[Row] = []
    families: dict[str, int] = {}
    skipped_links = 0
    for project in sorted(source.iterdir(), key=lambda path: (path.name.casefold(), path.name)):
        if project.name.startswith("."):
            continue
        if project.is_symlink():
            skipped_links += 1
            continue
        if not project.is_dir():
            continue
        languages = _languages(project)
        if languages:
            for language in languages:
                families[language] = families.get(language, 0) + 1
            projects.append(Row("Projects", "FOUND", project.name, ", ".join(languages)))

    if skipped_links:
        notes.append(f"{skipped_links} symbolic-link entries skipped.")
    count = len(projects)
    if count:
        rows = [Row("Languages", "DETECTED", language,
                    f"{total} {'project' if total == 1 else 'projects'}")
                for language, total in sorted(families.items(), key=lambda item: (-item[1], item[0]))]
        rows.extend(projects)
    else:
        rows = [Row("Projects", "EMPTY", "No manifests", "No supported language manifests found.")]
    summary = (f"{count} {'project' if count == 1 else 'projects'} · {len(families)} "
               f"{'language family' if len(families) == 1 else 'language families'}")
    return Report(
        command="projects", title="PROJECT INVENTORY",
        status="INVENTORY" if count else "EMPTY", summary=summary,
        next_action="Run orbit map --git for tool readiness and cached Git state." if count
                    else "Add a supported language manifest under the source directory.",
        notes=notes, rows=rows,
    )
