"""Read-only preview of profile selection and workstation configuration."""

from __future__ import annotations

import os
import plistlib
import re
import shlex
import subprocess
import sys
from pathlib import Path

from .report import Report, Row
from .state import resolve_profiles


class PlanError(Exception):
    """A managed-file preview could not be produced."""


PACKAGE_LINE = re.compile(r"(brew|cask|tap)\s+(['\"])([^'\"]+)\2(?:\s+(.*))?")
MAX_MANIFEST_BYTES = 128 * 1024
MAX_DEFAULTS_BYTES = 1024 * 1024


def _count(amount: int, singular: str, plural: str) -> str:
    return f"{amount} {singular if amount == 1 else plural}"


def _package_scope(root: Path, profiles: list[str]) -> tuple[list[Row], int]:
    """Inventory simple Brewfile declarations without evaluating Ruby or probing Homebrew."""
    scope_rows: list[Row] = []
    named_rows: list[Row] = []
    review_rows: list[Row] = []
    total = 0
    sources = [("Base", root / "Brewfile")]
    sources.extend((name, root / "profiles" / f"{name}.Brewfile") for name in profiles)
    for label, manifest in sources:
        relative = manifest.relative_to(root)
        if manifest.is_symlink() or not manifest.is_file():
            review_rows.append(Row("Manifest review", "REVIEW", label,
                                   f"{relative} is unavailable or a symbolic link; inspect before setup"))
            continue
        try:
            with manifest.open("rb") as source:
                content = source.read(MAX_MANIFEST_BYTES + 1)
            if len(content) > MAX_MANIFEST_BYTES:
                review_rows.append(Row("Manifest review", "REVIEW", label,
                                       f"{relative} exceeds the 128 KiB inventory limit"))
                continue
            lines = content.decode("utf-8").splitlines()
        except (OSError, UnicodeError):
            review_rows.append(Row("Manifest review", "REVIEW", label,
                                   f"{relative} could not be read; inspect before setup"))
            continue
        names: dict[str, list[str]] = {"brew": [], "cask": [], "tap": []}
        for number, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = PACKAGE_LINE.fullmatch(line)
            if match is None:
                review_rows.append(Row("Manifest review", "REVIEW", f"{relative}:{number}",
                                       "Declaration is not in the simple inventory; inspect source"))
                continue
            kind, _, name, remainder = match.groups()
            names[kind].append(name)
            total += 1
            if remainder and not remainder.startswith("#"):
                review_rows.append(Row("Manifest review", "REVIEW", f"{relative}:{number}",
                                       f"{name} has a condition or options; setup decides whether it applies"))
        scope_rows.append(Row("Package scope", "FOUND", label,
                              f"{_count(len(names['brew']), 'formula', 'formulae')} · "
                              f"{_count(len(names['cask']), 'cask', 'casks')} · "
                              f"{_count(len(names['tap']), 'tap', 'taps')}"))
        if names["cask"]:
            named_rows.append(Row("Casks and taps", "FOUND", f"{label} casks", ", ".join(names["cask"])))
        if names["tap"]:
            named_rows.append(Row("Casks and taps", "FOUND", f"{label} taps", ", ".join(names["tap"])))
    return scope_rows + named_rows + review_rows, total


def _managed_files(root: Path) -> list[Row]:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        result = subprocess.run(
            [str(root / "scripts/configure"), "--plan"], cwd=root, env=environment,
            capture_output=True, text=True, check=False, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PlanError("managed-file preview could not run") from error
    if result.returncode != 0:
        raise PlanError(result.stderr.strip() or "managed-file preview failed")
    rows: list[Row] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "No managed file changes.":
            rows.append(Row("Managed files", "UNCHANGED", "Managed configuration", "No file changes"))
        elif line.startswith(("CREATE ", "CHANGE ", "COPY ")):
            state, detail = line.split(None, 1)
            rows.append(Row("Managed files", state, "Destination", detail))
        else:
            rows.append(Row("Managed files", "NOTE", "Configurator", line))
    return rows or [Row("Managed files", "REVIEW", "Configurator", "No preview returned")]


def _current_preferences(domains: set[str]) -> dict[str, dict[str, object] | None]:
    """Read complete domains into memory without printing existing values."""
    observed: dict[str, dict[str, object] | None] = {}
    for domain in sorted(domains):
        try:
            result = subprocess.run(
                ["/usr/bin/defaults", "export", domain, "-"],
                capture_output=True, check=False, timeout=5,
            )
            if result.returncode != 0 or len(result.stdout) > MAX_DEFAULTS_BYTES:
                observed[domain] = None
                continue
            content = plistlib.loads(result.stdout)
            observed[domain] = content if isinstance(content, dict) else None
        except (OSError, subprocess.TimeoutExpired, plistlib.InvalidFileException, ValueError):
            observed[domain] = None
    return observed


def _macos_preferences(root: Path) -> tuple[list[Row], int]:
    """Compare the action's scalar declarations with local macOS values where possible."""
    action = root / "scripts/macos-defaults"
    if action.is_symlink() or not action.is_file():
        return [Row("macOS preferences", "REVIEW", "Action",
                    "scripts/macos-defaults is unavailable or a symbolic link")], 0
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        result = subprocess.run(
            ["/bin/bash", str(action), "--plan"], cwd=root, env=environment,
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [Row("macOS preferences", "REVIEW", "Action",
                    "Preference preview could not run; inspect scripts/macos-defaults")], 0
    if result.returncode != 0:
        return [Row("macOS preferences", "REVIEW", "Action",
                    "Preference preview failed; inspect scripts/macos-defaults")], 0

    rows: list[Row] = []
    declarations: list[tuple[str, str, str, str, object]] = []
    for number, line in enumerate(result.stdout.splitlines(), start=1):
        parts = line.split("\t")
        if len(parts) != 4 or not all(parts) or parts[2] not in {"bool", "int", "string"}:
            rows.append(Row("macOS preferences", "REVIEW", f"Declaration {number}",
                            "Unrecognized preference declaration; inspect scripts/macos-defaults"))
            continue
        domain, key, value_type, value = parts
        if value_type == "bool" and value not in {"true", "false"}:
            rows.append(Row("macOS preferences", "REVIEW", f"Declaration {number}",
                            "Invalid boolean preference; inspect scripts/macos-defaults"))
            continue
        try:
            expected: object = ({"true": True, "false": False}[value] if value_type == "bool"
                                else int(value) if value_type == "int" else value)
        except ValueError:
            rows.append(Row("macOS preferences", "REVIEW", f"Declaration {number}",
                            "Invalid integer preference; inspect scripts/macos-defaults"))
            continue
        declarations.append((domain, key, value_type, value, expected))

    current = (_current_preferences({item[0] for item in declarations})
               if sys.platform == "darwin" else {})
    if sys.platform == "darwin":
        for domain, content in current.items():
            if content is None:
                rows.append(Row("macOS preferences", "REVIEW", domain,
                                "Current values unavailable; showing declared values only"))
    missing = object()
    for domain, key, value_type, value, expected in declarations:
        content = current.get(domain)
        if content is None:
            state = "PREVIEW"
        else:
            actual = content.get(key, missing)
            state = ("CREATE" if actual is missing else "MATCH"
                     if type(actual) is type(expected) and actual == expected else "CHANGE")
        rows.append(Row("macOS preferences", state, key,
                        f"{domain} · {value_type} {value}"))
    if not rows:
        rows.append(Row("macOS preferences", "REVIEW", "Action",
                        "No preference declarations returned"))
    return rows, len(declarations)


def build_report(root: Path, arguments: list[str]) -> Report:
    existing = resolve_profiles(root, [])
    desired = resolve_profiles(root, arguments)
    rows: list[Row] = []
    for name in desired:
        rows.append(Row("Profiles", "ENABLED" if name in existing else "SELECT", name,
                        f"profiles/{name}.Brewfile"))
    if not desired:
        rows.append(Row("Profiles", "BASE", "Base Brewfile", "No optional profiles selected"))
    package_rows, declarations = _package_scope(root, desired)
    rows.extend(package_rows)
    rows.extend(_managed_files(root))
    preference_rows, preferences = _macos_preferences(root)
    rows.extend(preference_rows)
    changes = sum(row.group == "Managed files" and row.state in {"CREATE", "CHANGE", "COPY"}
                  for row in rows)
    preference_changes = sum(row.state in {"CREATE", "CHANGE"} for row in preference_rows)
    preference_summary = _count(preferences, "macOS preference", "macOS preferences")
    if preferences and all(row.state in {"CREATE", "CHANGE", "MATCH"}
                           for row in preference_rows):
        preference_summary += f" ({_count(preference_changes, 'difference', 'differences')})"
    new_profiles = [name for name in desired if name not in existing]
    flags = " ".join(f"--profile {shlex.quote(name)}" for name in new_profiles)
    action = f"cd {shlex.quote(str(root))} && ./setup"
    if flags:
        action += f" {flags}"
    return Report(
        command="plan", title="PLAN", status="PREVIEW",
        summary=(f"{_count(len(new_profiles), 'new profile', 'new profiles')} · "
                 f"{_count(changes, 'managed file change', 'managed file changes')} · "
                 f"{_count(declarations, 'Homebrew declaration', 'Homebrew declarations')} · "
                 f"{preference_summary}"),
        next_action=action,
        notes=["Homebrew inventory is static: no Ruby evaluation, installed-state check, or package resolution.",
               "Managed file preview shows destinations and backup intent, never file or backup contents.",
               "macOS preferences compare current values where readable; existing values stay private.",
               "Setup backs up affected preference domains, then writes every declared key.",
               "Setup also installs runtimes and starts services."],
        rows=rows,
    )
