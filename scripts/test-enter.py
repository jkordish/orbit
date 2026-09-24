"""Focused checks for the read-only project entry view."""

import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location("orbit_enter", Path(__file__).with_name("enter.py"))
assert spec and spec.loader
enter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enter)


def inspect(project, orbit, answers, selected=""):
    (orbit / "profiles").mkdir(exist_ok=True)
    (orbit / "profiles/wasm.Brewfile").write_text("")
    (orbit / "config").mkdir(exist_ok=True)
    (orbit / "config/profiles.txt").write_text(selected)
    before = sorted((str(path.relative_to(project)), path.stat().st_mtime_ns)
                    for path in project.rglob("*") if path.is_file())
    output = io.StringIO()

    def fake_probe(command, *arguments):
        if command == "docker" and arguments[:2] == ("context", "inspect"):
            return answers.get("docker_context", (True, "unix:///var/run/docker.sock"))
        return answers.get(command, (False, "command unavailable"))

    with mock.patch.object(enter, "ORBIT_ROOT", orbit), mock.patch.object(enter, "probe", fake_probe), \
            mock.patch.object(enter.shutil, "which", lambda command: f"/fake/{command}"), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        code = enter.main([str(project)])
    after = sorted((str(path.relative_to(project)), path.stat().st_mtime_ns)
                   for path in project.rglob("*") if path.is_file())
    assert before == after, "enter changed a project file"
    return code, output.getvalue()


with tempfile.TemporaryDirectory(prefix="orbit enter ") as temporary:
    base = Path(temporary)
    project = base / "project"
    orbit = base / "orbit"
    project.mkdir()
    orbit.mkdir()
    (project / "Cargo.toml").write_text("[package]\nname = 'example'\n")
    (project / "rust-toolchain.toml").write_text('[toolchain]\nchannel = "stable"\n')
    (project / "package.json").write_text(json.dumps({
        "engines": {"node": ">=20"}, "packageManager": "pnpm@12.3.4",
        "scripts": {"postinstall": "touch SHOULD_NOT_EXIST"},
    }))
    (project / "go.mod").write_text("module example.org/test\ngo 1.27\n")
    (project / "pyproject.toml").write_text("[project]\nrequires-python = '>=3.12,<4'\n")
    (project / ".python-version").write_text("3.14\n")
    (project / "Package.swift").write_text("// swift-tools-version: 6.2\n// arbitrary project code; never run\n")
    (project / "flake.nix").write_text("# arbitrary project code; never run\n")
    (project / "compose.yaml").write_text("services: {}\n")
    (project / ".orbit.json").write_text(json.dumps({
        "version": 1, "profiles": ["wasm"], "services": ["container"],
    }))
    (project / "node_modules").mkdir()
    (project / "node_modules/package.json").write_text("{}")
    answers = {
        "rustup": (True, "stable-aarch64-apple-darwin (default)"),
        "node": (True, "v24.21.0"),
        "go": (True, "go version go1.27.1 darwin/arm64"),
        "python3": (True, "Python 3.14.7"),
        "pnpm": (True, "12.3.4"),
        "xcrun": (True, "Apple Swift version 6.2.1"),
        "nix": (True, "nix 2.29.0"),
        "docker": (True, "28.0.0"),
        "container": (True, "status running"),
    }
    code, result = inspect(project, orbit, answers, "wasm\n")
    assert code == 0, result
    assert "TOOLING READY" in result and "node_modules" not in result, result
    assert not (project / "SHOULD_NOT_EXIST").exists()

    code, result = inspect(project, orbit, answers)
    assert code == 1 and "SELECT   profile/wasm" in result, result
    assert "./setup --profile wasm" in result, result

    mismatched = dict(answers, node=(True, "v18.0.0"))
    code, result = inspect(project, orbit, mismatched, "wasm\n")
    assert code == 1 and "MISMATCH Node" in result, result

    old_python_pin = (project / ".python-version").read_text()
    (project / ".python-version").unlink()
    old_python = dict(answers, python3=(True, "Python 3.11.8"))
    code, result = inspect(project, orbit, old_python, "wasm\n")
    assert code == 1 and "MISMATCH Python" in result, result
    (project / ".python-version").write_text(old_python_pin)

    old_swift = dict(answers, xcrun=(True, "Apple Swift version 5.9"))
    code, result = inspect(project, orbit, old_swift, "wasm\n")
    assert code == 1 and "MISMATCH Swift" in result, result

    remote_context = dict(answers, docker_context=(True, "ssh://remote.example"))
    code, result = inspect(project, orbit, remote_context, "wasm\n")
    assert code == 1 and "not a confirmed local Unix socket" in result, result

    (project / "package.json").write_text(json.dumps({"engines": {"node": "^24 || ^26"}}))
    code, result = inspect(project, orbit, answers, "wasm\n")
    assert code == 1 and "needs manual review" in result, result

    (project / ".orbit.json").write_text(json.dumps({"version": 1, "hooks": ["malicious"]}))
    code, result = inspect(project, orbit, answers, "wasm\n")
    assert code == 2 and "only version, profiles, and services" in result, result

    (project / ".orbit.json").unlink()
    (project / "go.mod").unlink()
    (project / "go.mod").symlink_to(base / "elsewhere")
    code, result = inspect(project, orbit, answers, "wasm\n")
    assert code == 1 and "Skipped symbolic link go.mod" in result, result

print("Project entry checked ready, mismatch, review, invalid input, and symlink cases.")
