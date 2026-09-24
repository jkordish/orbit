"""Read-only, bounded project tooling inventory for ``orbit enter``.

This intentionally checks tool availability, not dependency installation or build health.
Project files are treated as untrusted data; no project command is executed.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import stat
import subprocess
from pathlib import Path

from .report import Report, Row
from .state import selected_profiles

ORBIT_ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_BYTES = 128 * 1024
MAX_DIRS = 256
MAX_MANIFESTS = 96
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "target",
    "dist", "build", ".build", ".next", ".turbo", ".cache", "vendor",
    "Pods", "DerivedData", "coverage", "__pycache__",
}
MANIFESTS = {
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "package.json": "Node",
    "pnpm-workspace.yaml": "Node",
    "Package.swift": "Swift",
    "flake.nix": "Nix",
    "compose.yaml": "Docker",
    "compose.yml": "Docker",
    "docker-compose.yaml": "Docker",
    "docker-compose.yml": "Docker",
}
DECLARATIONS = {"rust-toolchain", "rust-toolchain.toml", ".python-version"}
TOOL_ORDER = ("Rust", "Node", "Go", "Python", "Swift", "Xcode", "Nix", "Docker", "container")


class InputError(Exception):
    """A project or declaration cannot be inspected safely."""


def display(value: object) -> str:
    """Keep untrusted filenames and declarations from controlling the terminal."""
    return json.dumps(str(value), ensure_ascii=False)[1:-1]


def read_small(path: Path) -> str:
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise InputError(f"{path.name} is not a regular file")
            contents = stream.read(MAX_FILE_BYTES + 1)
        if len(contents) > MAX_FILE_BYTES:
            raise InputError(f"{path.name} exceeds the 128 KiB read limit")
        return contents.decode("utf-8")
    except (OSError, UnicodeError) as error:
        reason = error.strerror if isinstance(error, OSError) else "invalid UTF-8"
        raise InputError(f"cannot safely read {display(path.name)}: {reason}") from error


def scan(root: Path) -> tuple[dict[str, list[Path]], list[Path], list[str]]:
    stacks: dict[str, list[Path]] = {}
    declarations: list[Path] = []
    reviews: list[str] = []
    queue = [(root, 0)]
    dirs = 0
    manifests = 0
    while queue:
        directory, depth = queue.pop(0)
        dirs += 1
        if dirs > MAX_DIRS:
            reviews.append("Directory scan stopped at 256 directories")
            break
        try:
            entries = sorted(directory.iterdir(), key=lambda path: path.name)
        except OSError:
            reviews.append(f"Cannot list {display(directory.relative_to(root))}")
            continue
        for path in entries:
            name = path.name
            if path.is_symlink():
                if name in MANIFESTS or name in DECLARATIONS:
                    reviews.append(f"Skipped symbolic link {display(path.relative_to(root))}")
                continue
            if path.is_dir():
                if name.endswith(".xcodeproj"):
                    stacks.setdefault("Xcode", []).append(path)
                elif depth < 2 and name not in SKIP_DIRS and not name.startswith("."):
                    queue.append((path, depth + 1))
                continue
            if name in MANIFESTS or name in DECLARATIONS:
                manifests += 1
                if manifests > MAX_MANIFESTS:
                    reviews.append("Manifest scan stopped at 96 files")
                    return stacks, declarations, reviews
                if name in MANIFESTS:
                    stacks.setdefault(MANIFESTS[name], []).append(path)
                else:
                    declarations.append(path)
    return stacks, declarations, reviews


def declaration(path: Path, root: Path, reviews: list[str]) -> str | None:
    try:
        return read_small(path)
    except InputError as error:
        reviews.append(f"{display(path.relative_to(root))}: {error}")
        return None


def project_requirements(
    root: Path, stacks: dict[str, list[Path]], declarations: list[Path], reviews: list[str],
) -> tuple[dict[str, list[tuple[str, Path]]], list[str], list[str]]:
    versions: dict[str, list[tuple[str, Path]]] = {}
    for path in stacks.get("Node", []):
        if path.name != "package.json":
            continue
        body = declaration(path, root, reviews)
        if body is None:
            continue
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeError):
            reviews.append(f"{display(path.relative_to(root))}: invalid JSON")
            continue
        if not isinstance(data, dict):
            reviews.append(f"{display(path.relative_to(root))}: expected a JSON object")
            continue
        engines = data.get("engines", {})
        if engines:
            if isinstance(engines, dict) and isinstance(engines.get("node"), str):
                versions.setdefault("Node", []).append((engines["node"], path))
            elif not isinstance(engines, dict) or "node" in engines:
                reviews.append(f"{display(path.relative_to(root))}: invalid Node engine declaration")
        manager = data.get("packageManager")
        if manager is not None:
            if isinstance(manager, str) and re.fullmatch(r"(pnpm|npm|yarn)@\d+(?:\.\d+){0,2}(?:\+.*)?", manager):
                tool, version = manager.split("@", 1)
                versions.setdefault(tool, []).append((version.split("+", 1)[0], path))
            else:
                reviews.append(f"{display(path.relative_to(root))}: unsupported packageManager declaration")
    for path in stacks.get("Go", []):
        body = declaration(path, root, reviews)
        if body is None:
            continue
        for keyword in ("go", "toolchain"):
            match = re.search(rf"(?m)^{keyword}\s+(?:go)?(\d+\.\d+(?:\.\d+)?)(?:\s*//[^\n]*)?$", body)
            if match:
                versions.setdefault("Go", []).append((f">={match.group(1)}", path))
            elif re.search(rf"(?m)^{keyword}\s+", body):
                reviews.append(f"{display(path.relative_to(root))}: {keyword} version needs manual review")
    for path in stacks.get("Python", []):
        if path.name != "pyproject.toml":
            continue
        body = declaration(path, root, reviews)
        if body is None:
            continue
        project_table = re.search(r"(?ms)^\[project\]\s*$(.*?)(?=^\[|\Z)", body)
        if project_table:
            match = re.search(r"(?m)^\s*requires-python\s*=\s*[\"']([^\"']+)[\"']", project_table.group(1))
            if match:
                versions.setdefault("Python", []).append((match.group(1), path))
            elif re.search(r"(?m)^\s*requires-python\s*=", project_table.group(1)):
                reviews.append(f"{display(path.relative_to(root))}: requires-python needs manual review")
    for path in stacks.get("Swift", []):
        body = declaration(path, root, reviews)
        if body is None:
            continue
        match = re.search(r"(?m)^//\s*swift-tools-version:\s*(\d+\.\d+(?:\.\d+)?)", body)
        if match:
            versions.setdefault("Swift", []).append((f">={match.group(1)}", path))
    for path in declarations:
        body = declaration(path, root, reviews)
        if body is None:
            continue
        if path.name == ".python-version":
            value = body.strip()
            if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", value):
                versions.setdefault("Python", []).append((value, path))
            else:
                reviews.append(f"{display(path.relative_to(root))}: Python version needs manual review")
        else:
            if path.name.endswith(".toml"):
                match = re.search(r"(?m)^\s*channel\s*=\s*[\"']([^\"']+)[\"']\s*$", body)
                value = match.group(1) if match else ""
            else:
                value = body.strip()
            if re.fullmatch(r"stable|\d+\.\d+(?:\.\d+)?", value):
                versions.setdefault("Rust", []).append((value, path))
            else:
                reviews.append(f"{display(path.relative_to(root))}: Rust channel needs manual review")

    profile_names = {path.name.removesuffix(".Brewfile") for path in (ORBIT_ROOT / "profiles").glob("*.Brewfile")}
    project_profiles: list[str] = []
    services: list[str] = []
    manifest = root / ".orbit.json"
    if manifest.exists() or manifest.is_symlink():
        body = read_small(manifest)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as error:
            raise InputError(f".orbit.json: invalid JSON: {error.msg}") from error
        if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
            raise InputError(".orbit.json: expected object with version 1")
        if set(data) - {"version", "profiles", "services"}:
            raise InputError(".orbit.json: only version, profiles, and services are supported")
        for key, allowed in (("profiles", profile_names), ("services", {"container", "docker"})):
            values = data.get(key, [])
            if not isinstance(values, list) or any(not isinstance(value, str) or value not in allowed for value in values):
                raise InputError(f".orbit.json: invalid {key} entry")
            if len(values) != len(set(values)):
                raise InputError(f".orbit.json: duplicate {key} entry")
            if key == "profiles":
                project_profiles = values
            else:
                services = values
    if "Docker" in stacks and "docker" not in services:
        services.append("docker")
    return versions, project_profiles, services


def installed_profiles() -> set[str]:
    return set(selected_profiles(ORBIT_ROOT))


def probe(command: str, *arguments: str) -> tuple[bool, str]:
    if shutil.which(command) is None:
        return False, "command unavailable"
    environment = dict(os.environ)
    environment.update({
        "MISE_AUTO_INSTALL": "0", "MISE_EXEC_AUTO_INSTALL": "0",
        "MISE_NOT_FOUND_AUTO_INSTALL": "0", "MISE_OFFLINE": "1",
        "GOTOOLCHAIN": "local", "UV_OFFLINE": "1", "UV_PYTHON_DOWNLOADS": "never",
        "COREPACK_ENABLE_NETWORK": "0", "HOMEBREW_NO_AUTO_UPDATE": "1",
    })
    environment.pop("DOCKER_HOST", None)
    environment.pop("DOCKER_CONTEXT", None)
    try:
        result = subprocess.run(
            [command, *arguments], cwd=ORBIT_ROOT, env=environment,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=4, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, "local check failed or timed out"
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, output[:400]


def numeric_version(value: str) -> tuple[int, ...] | None:
    match = re.search(r"(?:^|[^\d])(\d+\.\d+(?:\.\d+)?)", value)
    return tuple(int(part) for part in match.group(1).split(".")) if match else None


def first_line(value: str) -> str:
    return display(value.splitlines()[0]) if value.splitlines() else "no version detail"


def satisfies(actual: tuple[int, ...], requirement: str) -> bool | None:
    for clause in requirement.split(","):
        match = re.fullmatch(r"\s*(>=|<=|==|!=|>|<)?(\d+(?:\.\d+){0,2})(\.\*)?\s*", clause)
        if not match:
            return None
        operator = match.group(1) or "=="
        target = tuple(int(part) for part in match.group(2).split("."))
        if match.group(3) and operator not in {"==", "!="}:
            return None
        width = max(len(actual), len(target))
        left = actual + (0,) * (width - len(actual))
        right = target + (0,) * (width - len(target))
        equal = actual[:len(target)] == target if match.group(3) or match.group(1) is None else left == right
        outcomes = {
            ">=": left >= right, "<=": left <= right, ">": left > right,
            "<": left < right, "==": equal, "!=": not equal,
        }
        if not outcomes[operator]:
            return False
    return True


def build_report(root: Path) -> Report:
    stacks, declarations, reviews = scan(root)
    versions, profiles, services = project_requirements(root, stacks, declarations, reviews)
    required = set(stacks)
    if any(path.name.startswith("rust-toolchain") for path in declarations):
        required.add("Rust")
    if any(path.name == ".python-version" for path in declarations):
        required.add("Python")
    if "Xcode" in required:
        required.add("Swift")
    required.update(services)
    checks: list[tuple[str, str, str]] = []
    missing_base = False
    missing_service = False
    missing_special: list[str] = []
    mismatch = False

    for name in TOOL_ORDER:
        if name not in required:
            continue
        remote_docker = False
        if name == "Rust":
            ok, output = probe("rustup", "toolchain", "list")
            channels = [value for value, _ in versions.get("Rust", [("stable", root)])]
            present = ok and all(any(line.startswith((f"{channel}-", f"{channel} "))
                                     for line in output.splitlines()) for channel in channels)
            detail = ", ".join(channels) + " toolchain" if present else "required rustup toolchain unavailable"
        elif name == "Node":
            ok, output = probe("node", "--version")
            present = ok and numeric_version(output) is not None
            detail = first_line(output) if present else "node unavailable"
        elif name == "Go":
            ok, output = probe("go", "version")
            present = ok and numeric_version(output) is not None
            detail = first_line(output) if present else "go unavailable"
        elif name == "Python":
            ok, output = probe("python3", "--version")
            present = ok and numeric_version(output) is not None
            detail = first_line(output) if present else "python3 unavailable"
        elif name == "Swift":
            found, _ = probe("xcrun", "--find", "swift")
            ok, output = probe("xcrun", "swift", "--version") if found else (False, "")
            present = ok and numeric_version(output) is not None
            detail = first_line(output) if present else "Swift toolchain unavailable"
        elif name == "Xcode":
            ok, output = probe("xcodebuild", "-version")
            present = ok
            detail = first_line(output) if ok else "full Xcode unavailable"
        elif name == "Nix":
            ok, output = probe("nix", "--version")
            present = ok
            detail = first_line(output) if ok else "nix unavailable"
        elif name == "Docker":
            if shutil.which("docker") is None:
                present = False
                detail = "docker CLI unavailable"
            else:
                context_ok, endpoint = probe("docker", "context", "inspect", "default", "--format", "{{.Endpoints.docker.Host}}")
                if not context_ok or not endpoint.startswith("unix://"):
                    present = False
                    remote_docker = True
                    detail = "local Docker endpoint could not be confirmed"
                else:
                    ok, output = probe("docker", "--context", "default", "info", "--format", "{{.ServerVersion}}")
                    present = ok
                    detail = "local Docker daemon reachable" if ok else "local Docker daemon unavailable"
        else:
            ok, output = probe("container", "system", "status")
            present = ok and bool(re.search(r"(?m)^status\s+running\b", output))
            detail = "Apple container service running" if present else (
                "container CLI unavailable" if shutil.which("container") is None else "Apple container service stopped"
            )
        checks.append(("REVIEW" if remote_docker else "OK" if present else "MISSING", name, detail))
        if not present:
            if remote_docker:
                reviews.append("Docker default context is not a confirmed local Unix socket")
                continue
            if name in {"Docker", "container"} and shutil.which(name.lower()) is not None:
                missing_service = True
            elif name in {"Xcode", "Nix", "Swift"} or (name == "Rust" and channels != ["stable"]):
                missing_special.append(name if name != "Rust" else f"Rust {', '.join(channels)}")
            else:
                missing_base = True
            continue
        if name in {"Node", "Go", "Python", "Swift"}:
            actual = numeric_version(output)
            for requirement, path in versions.get(name, []):
                outcome = satisfies(actual, requirement) if actual else None
                source = display(path.relative_to(root))
                if outcome is False:
                    checks.append(("MISMATCH", name, f"{source} requires {requirement}"))
                    mismatch = True
                elif outcome is None:
                    reviews.append(f"{source}: {name} range {display(requirement)} needs manual review")

    for manager in ("pnpm", "npm", "yarn"):
        if manager not in versions:
            continue
        ok, output = probe(manager, "--version")
        actual = numeric_version(output) if ok else None
        if actual is None:
            checks.append(("MISSING", manager, "package manager unavailable"))
            if manager == "yarn":
                missing_special.append("yarn")
            else:
                missing_base = True
            continue
        checks.append(("OK", manager, first_line(output)))
        for requirement, path in versions[manager]:
            if satisfies(actual, requirement) is False:
                checks.append(("MISMATCH", manager, f"{display(path.relative_to(root))} requires {requirement}"))
                mismatch = True

    selected = installed_profiles()
    missing_profiles = [name for name in profiles if name not in selected]
    for name in profiles:
        checks.append(("SELECT" if name in missing_profiles else "SELECTED", f"profile/{name}", "project declaration"))
    for issue in reviews:
        checks.append(("REVIEW", "declaration", issue))

    rows: list[Row] = []
    if stacks:
        for name, paths in stacks.items():
            preview = ", ".join(str(path.relative_to(root)) for path in paths[:3])
            suffix = f" (+{len(paths) - 3} more)" if len(paths) > 3 else ""
            rows.append(Row("Stack", "DETECTED", name, f"{preview}{suffix}"))
    elif declarations or profiles or services:
        rows.append(Row("Stack", "DECLARED", "Project requirements", "No language manifests"))
    else:
        rows.append(Row("Stack", "REVIEW", "No recognized manifests", "Add a supported manifest or .orbit.json"))
    for state, name, detail in checks:
        rows.append(Row("Readiness", state, name, detail))
    if not checks:
        rows.append(Row("Readiness", "REVIEW", "No requirements", "Project tooling cannot be confirmed"))

    command_root = shlex.quote(str(ORBIT_ROOT))
    if missing_profiles:
        flags = " ".join(f"--profile {shlex.quote(name)}" for name in missing_profiles)
        next_action = f"cd {command_root} && ./setup {flags}"
    elif missing_base:
        next_action = f"cd {command_root} && ./setup"
    elif missing_special:
        next_action = f"Install or select {missing_special[0]} for this project"
    elif missing_service:
        if any(state == "MISSING" and name == "Docker" for state, name, _ in checks):
            next_action = f"cd {command_root} && ./scripts/services enable colima"
        else:
            next_action = f"cd {command_root} && ./scripts/services enable container"
    elif mismatch or reviews:
        next_action = "Review the declaration above and select its project-compatible toolchain"
    elif not checks:
        next_action = "Add a supported manifest or .orbit.json to declare tooling"
    else:
        next_action = "Open the project; run its own dependency and build checks when needed"
    ready = bool(checks) and not (missing_base or missing_service or missing_special or mismatch or reviews or missing_profiles)
    return Report(
        command="enter", title="PROJECT ENTRY", status="TOOLING READY" if ready else "ACTION NEEDED",
        summary="Local project tooling", next_action=next_action, exit_code=0 if ready else 1,
        notes=[f"Project: {root}", "Scope: toolchains, profile selection, and requested services",
               "Scan: project root and two directory levels; generated folders skipped",
               "Project code, dependencies, builds, and services were unchanged."],
        rows=rows,
    )
