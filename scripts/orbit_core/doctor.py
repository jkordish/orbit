"""Read-only machine readiness checks shared by text and JSON views."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .report import Report, Row
from .state import selected_profiles


def _probe(root: Path, arguments: list[str], *, timeout: int = 30) -> tuple[bool, str]:
    environment = dict(os.environ)
    environment.update({
        "HOMEBREW_NO_AUTO_UPDATE": "1", "HOMEBREW_BUNDLE_NO_UPGRADE": "1",
        "MISE_AUTO_INSTALL": "0", "MISE_EXEC_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_AUTO_INSTALL": "0", "MISE_OFFLINE": "1",
        "RUSTUP_AUTO_INSTALL": "0", "GOTOOLCHAIN": "local",
        "UV_OFFLINE": "1", "UV_PYTHON_DOWNLOADS": "never",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    try:
        result = subprocess.run(
            arguments, cwd=root, env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, check=False, timeout=timeout,
        )
    except FileNotFoundError:
        return False, f"{Path(arguments[0]).name} unavailable"
    except (OSError, subprocess.TimeoutExpired):
        return False, f"{Path(arguments[0]).name} failed or timed out"
    output = result.stdout.rstrip("\n")
    if result.stderr:
        output += ("\n" if output else "") + result.stderr.rstrip("\n")
    return result.returncode == 0, output[:4096]


def _repository(root: Path) -> tuple[Row, str]:
    ok, output = _probe(root, [str(root / "scripts/repository-status"), str(root)])
    if not ok:
        return Row("Repository", "UNAVAILABLE", "Git checkout", "Git status unavailable"), "Inspect this Git checkout manually."
    fields = output.split("\t", 2)
    if len(fields) != 3:
        return Row("Repository", "UNAVAILABLE", "Git checkout", "Git status unavailable"), "Inspect this Git checkout manually."
    state, detail, action = fields
    return Row("Repository", state, "Git checkout", detail), action


def build_report(root: Path, *, docker: bool = False) -> Report:
    """Inspect the machine without installing, fetching, or starting services."""
    del docker  # Accepted for compatibility with the existing status command.
    repository, repository_action = _repository(root)
    rows = [repository]
    total = 0
    passed = 0
    next_action = ""

    def required(group: str, label: str, action: str, arguments: list[str], *, timeout: int = 30) -> None:
        nonlocal total, passed, next_action
        total += 1
        ok, output = _probe(root, arguments, timeout=timeout)
        if ok:
            passed += 1
            detail = output.splitlines()[0][:100] if output else "available"
        else:
            detail = output or "local check failed"
            if not next_action:
                next_action = action
        rows.append(Row(group, "PASS" if ok else "FAIL", label, detail))

    apply_action = "Run './scripts/apply', then rerun './scripts/doctor'."
    required("Foundation", "Apple developer tools", "Run 'xcode-select --install', then rerun './scripts/doctor'.",
             ["xcrun", "--find", "clang"])
    brew_action = apply_action if shutil.which("brew") else "Run './bootstrap.command', then rerun './scripts/doctor'."
    required("Foundation", "Brewfile packages", brew_action,
             ["brew", "bundle", "check", f"--file={root / 'Brewfile'}"], timeout=60)
    required("Foundation", "Optional profiles", apply_action,
             [str(root / "scripts/profiles"), "--check"], timeout=60)

    if "java" in selected_profiles(root):
        ok, prefix = _probe(root, ["brew", "--prefix", "openjdk@21"])
        java_binary = Path(prefix.splitlines()[0]) / "libexec/openjdk.jdk/Contents/Home/bin/java" if ok else Path("/nonexistent/java")
        required("Foundation", "Java runtime", apply_action, [str(java_binary), "-version"])

    for label, arguments in (
        ("Node", ["node", "--version"]),
        ("Go", ["go", "version"]),
        ("pnpm", ["pnpm", "--version"]),
    ):
        required("Languages", label, apply_action,
                 ["mise", "exec", "--no-deps", "--cd", str(root / "config"), "--", *arguments])
    required("Languages", "Stable Rust", apply_action, ["rustc", "+stable", "--version"])
    required("Languages", "Pinned Cargo utilities", apply_action,
             [str(root / "templates/python/.venv/bin/python"), str(root / "scripts/rust-tools.py"), "--check"])
    required("Containers", "Docker Compose", apply_action, ["docker", "compose", "version"])

    foundation_models = Path("/usr/bin/fm")
    if foundation_models.is_file():
        ok, detail = _probe(root, [str(foundation_models), "license", "--status"])
        lower = detail.lower()
        if "not agreed" in lower:
            rows.append(Row("Platform", "CONSENT NEEDED", "Apple Foundation Models",
                            "Review the system-wide terms yourself with 'sudo /usr/bin/fm license'."))
        elif "agreed to license" in lower and ok:
            rows.append(Row("Platform", "TERMS ACCEPTED", "Apple Foundation Models", "System-wide terms accepted"))
        else:
            rows.append(Row("Platform", "STATUS UNKNOWN", "Apple Foundation Models",
                            "Inspect /usr/bin/fm license --status manually."))
    else:
        rows.append(Row("Platform", "NOT INCLUDED", "Apple Foundation Models", "fm CLI unavailable"))

    if not next_action:
        next_action = repository_action or "All set. No changes needed."
    return Report(
        command="status", title="MACHINE READINESS",
        status="READY" if passed == total else "ATTENTION",
        summary=f"{passed}/{total} required checks passed",
        next_action=next_action, exit_code=0 if passed == total else 1,
        notes=["Read-only machine check. Package state may change after this report."],
        rows=rows,
    )
