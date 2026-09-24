"""One result shape for human and machine-readable Orbit views."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import TextIO


@dataclass(frozen=True)
class Row:
    group: str
    state: str
    label: str
    detail: str = ""


@dataclass
class Report:
    command: str
    title: str
    status: str
    summary: str
    next_action: str
    exit_code: int = 0
    notes: list[str] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": 1, **asdict(self)}


def _safe(value: str) -> str:
    """Keep untrusted project paths and command output from controlling a terminal."""
    return "".join(character if character.isprintable() else f"\\u{ord(character):04x}" for character in value)


def _color(value: str, name: str, stream: TextIO) -> str:
    if not stream.isatty() or "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return value
    colors = {
        "indigo": "\033[38;2;180;190;254m",
        "mint": "\033[38;2;148;226;213m",
        "amber": "\033[38;2;249;226;175m",
        "rose": "\033[38;2;243;139;168m",
    }
    return f"{colors[name]}{value}\033[0m"


def render(report: Report, *, json_output: bool = False, stream: TextIO | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    if json_output:
        json.dump(report.to_dict(), stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
        return

    stream.write(f"{_color('ORBIT', 'indigo', stream)} / {_safe(report.title)}\n")
    status_color = "mint" if report.exit_code == 0 else "rose"
    stream.write(f"  {_color(_safe(report.status), status_color, stream)} · {_safe(report.summary)}\n")
    for note in report.notes:
        stream.write(f"  {_safe(note)}\n")
    previous_group = ""
    for row in report.rows:
        if row.group != previous_group:
            stream.write(f"\n{_color(_safe(row.group.upper()), 'indigo', stream)}\n")
            previous_group = row.group
        if row.state in {"PASS", "OK", "ENABLED", "SELECTED", "SYNCED", "TERMS ACCEPTED", "READY"}:
            color = "mint"
        elif row.state in {"FAIL", "MISSING", "MISMATCH", "ACTION"}:
            color = "rose"
        else:
            color = "amber"
        state = _color(f"{_safe(row.state):<11}", color, stream)
        detail_lines = row.detail.splitlines() or [""]
        stream.write(f"  {state} {_safe(row.label):<24} {_safe(detail_lines[0])}\n")
        for line in detail_lines[1:]:
            stream.write(f"{'':<39}{_safe(line)}\n")
    stream.write(f"\nNEXT  {_safe(report.next_action)}\n")
