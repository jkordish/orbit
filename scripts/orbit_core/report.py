"""One result shape for human and machine-readable Orbit views."""

from __future__ import annotations

import json
import os
import shutil
import sys
import unicodedata
from collections import Counter
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


GOOD_STATES = {"PASS", "OK", "ENABLED", "SELECTED", "SYNCED", "TERMS ACCEPTED", "READY", "MATCH",
               "UNCHANGED", "TOOLING READY", "WORKSPACE READY"}
BAD_STATES = {"FAIL", "MISSING", "MISMATCH", "ACTION", "DIRTY", "DIVERGED", "AHEAD", "BEHIND",
              "UNAVAILABLE", "CONSENT NEEDED", "ACTION NEEDED", "ATTENTION", "ERROR"}
PREVIEW_STATES = {"PREVIEW", "SELECT", "CREATE", "CHANGE", "COPY", "DETECTED"}
COLORS = {
    "indigo": "\033[38;2;180;190;254m",
    "mint": "\033[38;2;148;226;213m",
    "amber": "\033[38;2;249;226;175m",
    "rose": "\033[38;2;243;139;168m",
    "muted": "\033[38;2;166;173;200m",
}


def _safe(value: str) -> str:
    """Keep untrusted project paths and command output from controlling a terminal."""
    return "".join(character if character.isprintable() else f"\\u{ord(character):04x}" for character in value)


def _color(value: str, name: str, stream: TextIO) -> str:
    if not stream.isatty() or "NO_COLOR" in os.environ or os.environ.get("TERM") == "dumb":
        return value
    return f"{COLORS[name]}{value}\033[0m"


def _tone(state: str, exit_code: int = 0) -> str:
    if state in GOOD_STATES:
        return "mint"
    if state in BAD_STATES:
        return "rose"
    if state in PREVIEW_STATES:
        return "indigo"
    if exit_code != 0 and state not in {"REVIEW", "EMPTY"}:
        return "rose"
    return "amber"


def _cells(value: str) -> int:
    return sum(0 if unicodedata.combining(character) else
               2 if unicodedata.east_asian_width(character) in {"F", "W"} else 1
               for character in value)


def _take_cells(value: str, limit: int) -> tuple[str, str]:
    width = 0
    for index, character in enumerate(value):
        size = _cells(character)
        if width + size > limit:
            return value[:index], value[index:]
        width += size
    return value, ""


def _clip(value: str, limit: int) -> str:
    if _cells(value) <= limit:
        return value
    if limit <= 1:
        return "…"
    first, _ = _take_cells(value, limit - 1)
    return first + "…"


def _pad(value: str, width: int) -> str:
    return value + " " * max(0, width - _cells(value))


def _wrap(value: str, width: int) -> list[str]:
    """Wrap already escaped text without measuring ANSI codes as content."""
    width = max(1, width)
    remaining = value.strip()
    if not remaining:
        return [""]
    lines: list[str] = []
    while remaining:
        if _cells(remaining) <= width:
            lines.append(remaining)
            break
        prefix, rest = _take_cells(remaining, width)
        if not prefix:
            prefix, rest = remaining[:1], remaining[1:]
        cut = prefix.rfind(" ")
        if cut > 0:
            lines.append(prefix[:cut].rstrip())
            remaining = remaining[cut + 1:].lstrip()
        else:
            lines.append(prefix)
            remaining = rest.lstrip()
    return lines


def _render_plain(report: Report, stream: TextIO) -> None:
    """Stable, line-oriented output for pipes and basic terminals."""
    stream.write(f"ORBIT / {_safe(report.title)}\n")
    stream.write(f"  {_safe(report.status)} · {_safe(report.summary)}\n")
    stream.writelines(f"  {_safe(note)}\n" for note in report.notes)
    previous_group = ""
    for row in report.rows:
        if row.group != previous_group:
            stream.write(f"\n{_safe(row.group.upper())}\n")
            previous_group = row.group
        detail_lines = row.detail.splitlines() or [""]
        stream.write(f"  {_safe(row.state):<11} {_safe(row.label):<24} {_safe(detail_lines[0])}\n")
        stream.writelines(f"{'':<39}{_safe(line)}\n" for line in detail_lines[1:])
    stream.write(f"\nNEXT  {_safe(report.next_action)}\n")


def _box_line(stream: TextIO, value: str, width: int, tone: str | None = None) -> None:
    content = _pad("  " + _clip(value, width - 4), width - 2)
    stream.write(f"│{_color(content, tone, stream) if tone else content}│\n")


def _render_tty(report: Report, stream: TextIO) -> None:
    width = max(12, min(shutil.get_terminal_size(fallback=(96, 24)).columns, 104))
    title = _clip(f" ◉ ORBIT / {_safe(report.title)} ", width - 3)
    stream.write(_color("╭─" + title + "─" * (width - 3 - _cells(title)) + "╮", "indigo", stream) + "\n")
    _box_line(stream, f"● {_safe(report.status)}", width, _tone(report.status, report.exit_code))
    for segment in _wrap(_safe(report.summary), width - 4):
        _box_line(stream, segment, width)
    stream.write(_color("╰" + "─" * (width - 2) + "╯", "indigo", stream) + "\n")

    for note in report.notes:
        for index, segment in enumerate(_wrap(_safe(note), width - 4)):
            marker = _color("·", "muted", stream) if index == 0 else " "
            stream.write(f"  {marker} {segment}\n")

    group_counts = Counter(row.group for row in report.rows)
    previous_group = ""
    for row in report.rows:
        if row.group != previous_group:
            heading = f"{_safe(row.group.upper())}  {group_counts[row.group]}"
            rule = "─" * max(0, width - 4 - _cells(heading))
            stream.write(f"\n  {_color(heading, 'indigo', stream)} {_color(rule, 'muted', stream)}\n")
            previous_group = row.group

        tone = _tone(row.state)
        icon = "●" if tone in {"mint", "rose"} else "◇"
        state = _safe(row.state)
        label = _safe(row.label)
        details = row.detail.splitlines() or [""]
        if width >= 72 and _cells(state) <= 14 and _cells(label) <= 24:
            left = f"  {icon} {_pad(state, 14)} {_pad(label, 24)} "
            prefix_width = _cells(left)
            colored_left = f"  {_color(icon + ' ' + _pad(state, 14), tone, stream)} {_pad(label, 24)} "
            first = True
            for detail in details:
                for segment in _wrap(_safe(detail), width - prefix_width):
                    stream.write(f"{colored_left if first else ' ' * prefix_width}{segment}\n")
                    first = False
        else:
            for index, segment in enumerate(_wrap(f"{icon} {state}  {label}", width - 2)):
                stream.write(f"  {_color(segment, tone, stream) if index == 0 else segment}\n")
            for detail in details:
                if detail:
                    for segment in _wrap(_safe(detail), width - 6):
                        stream.write(f"      {segment}\n")

    rule = "─" * max(0, width - 8)
    stream.write(f"\n  {_color('NEXT', 'indigo', stream)} {_color(rule, 'muted', stream)}\n")
    for index, segment in enumerate(_wrap(_safe(report.next_action), width - 4)):
        prefix = _color('↳', 'amber', stream) if index == 0 else ' '
        stream.write(f"  {prefix} {segment}\n")


def render(report: Report, *, json_output: bool = False, stream: TextIO | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    if json_output:
        json.dump(report.to_dict(), stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
    elif stream.isatty() and os.environ.get("TERM") != "dumb":
        _render_tty(report, stream)
    else:
        _render_plain(report, stream)
