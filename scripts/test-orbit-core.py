"""Check the shared report contract and isolated machine readiness behavior."""

import contextlib
import io
import json
import os
import re
import tempfile
from pathlib import Path
from unittest import mock

from orbit_core import cli, doctor
from orbit_core import report as report_ui
from orbit_core.report import Report, Row, render

with tempfile.TemporaryDirectory(prefix="orbit core ") as temporary:
    root = Path(temporary)
    (root / "config").mkdir()
    (root / "config/profiles.txt").write_text("java\n")
    observed = []

    def fake_probe(_root, arguments, **_kwargs):
        observed.append(tuple(arguments))
        command = str(arguments[0])
        if command.endswith("repository-status"):
            return True, "SYNCED\tmain = origin/main\t"
        if arguments[:3] == ["brew", "--prefix", "openjdk@21"]:
            return True, "/fake/homebrew/opt/openjdk@21"
        if command.endswith("rust-tools.py") or any(str(arg).endswith("rust-tools.py") for arg in arguments):
            return False, "MISSING/MISMATCH: cargo-auditable 0.7.5"
        if command == "/usr/bin/fm":
            return True, "Agreed to license"
        return True, "available"

    with mock.patch.object(doctor, "_probe", fake_probe), \
            mock.patch.object(doctor.shutil, "which", return_value="/fake/brew"):
        report = doctor.build_report(root)

    assert report.status == "ATTENTION"
    assert report.summary == "9/10 required checks passed", report.summary
    assert report.next_action == "Run './scripts/apply', then rerun './scripts/doctor'."
    assert any(row.state == "FAIL" and row.label == "Pinned Cargo utilities" for row in report.rows)
    assert not any("install" in arguments[0] for arguments in observed)
    assert set(root.rglob("*")) == {root / "config", root / "config/profiles.txt"}

    output = io.StringIO()
    render(report, json_output=True, stream=output)
    parsed = json.loads(output.getvalue())
    assert parsed["schema_version"] == 1 and parsed["exit_code"] == 1
    assert parsed["rows"][0]["state"] == "SYNCED"

    (root / "scripts").mkdir()
    repository_status = root / "scripts/repository-status"
    repository_status.write_text("#!/bin/sh\nprintf 'SYNCED\\tmain = origin/main\\t\\n'\n")
    repository_status.chmod(0o755)
    actual_row, actual_action = doctor._repository(root)
    assert actual_row.state == "SYNCED" and actual_action == ""

    invalid = io.StringIO()
    with contextlib.redirect_stdout(invalid):
        code = cli.main(["plan", "--json", "--profile"])
    assert code == 2
    assert json.loads(invalid.getvalue())["status"] == "ERROR"

    malicious = Report("enter", "ENTRY", "READY", "preview", "next", rows=[
        Row("Stack", "OK", "project", 'safe "quote"\x1b[31m'),
    ])
    text_output = io.StringIO()
    render(malicious, stream=text_output)
    assert 'safe "quote"\\u001b[31m' in text_output.getvalue()
    assert "\x1b" not in text_output.getvalue()

    class TerminalBuffer(io.StringIO):
        def isatty(self):
            return True

    styled = TerminalBuffer()
    with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True), \
            mock.patch.object(report_ui.shutil, "get_terminal_size", return_value=os.terminal_size((80, 24))):
        render(malicious, stream=styled)
    raw = styled.getvalue()
    uncolored = re.sub(r"\x1b\[[\d;]*m", "", raw)
    assert "\x1b[" in raw and "\x1b[31m" not in raw
    assert "╭─ ◉ ORBIT / ENTRY" in uncolored and "NEXT" in uncolored
    assert 'safe "quote"\\u001b[31m' in uncolored
    assert all(report_ui._cells(line) <= 80 for line in uncolored.splitlines())

    narrow_report = Report("map", "WORKSPACE MAP", "ACTION NEEDED", "One project needs review",
                           "Inspect the project and resolve its local tool requirements before continuing",
                           notes=["Read-only inspection across narrow terminals."],
                           rows=[Row("Projects", "REVIEW", "日本語-project-name",
                                     "A long detail that should wrap cleanly even when the terminal is narrow.")])
    narrow = TerminalBuffer()
    with mock.patch.dict(os.environ, {"TERM": "xterm-256color", "NO_COLOR": "1"}, clear=True), \
            mock.patch.object(report_ui.shutil, "get_terminal_size", return_value=os.terminal_size((48, 24))):
        render(narrow_report, stream=narrow)
    assert "\x1b" not in narrow.getvalue() and "╭─" in narrow.getvalue()
    assert all(report_ui._cells(line) <= 48 for line in narrow.getvalue().splitlines())
    assert "before continuing" in narrow.getvalue()

    basic = TerminalBuffer()
    with mock.patch.dict(os.environ, {"TERM": "dumb"}, clear=True):
        render(malicious, stream=basic)
    assert basic.getvalue().startswith("ORBIT / ENTRY\n") and "╭─" not in basic.getvalue()

    machine = TerminalBuffer()
    with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True):
        render(malicious, json_output=True, stream=machine)
    assert json.loads(machine.getvalue())["rows"][0]["detail"] == 'safe "quote"\x1b[31m'
    assert "╭─" not in machine.getvalue()

print("Shared Orbit reports, JSON errors, and read-only doctor checks passed.")
