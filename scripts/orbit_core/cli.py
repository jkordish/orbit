"""Dispatch Orbit's read-only views through one output contract."""

from __future__ import annotations

import sys
from pathlib import Path

from . import ORBIT_ROOT, doctor, enter, inventory, plan, workspace
from .report import Report, render
from .state import ProfileError

HELP = {
    "status": "Usage: orbit status [--docker] [--json]\nInspect machine readiness without changing it.",
    "plan": "Usage: orbit plan [--profile NAME|all]... [--details] [--json]\nPreview setup; --details shows every macOS preference.",
    "enter": "Usage: orbit enter [PROJECT_DIRECTORY] [--json]\nInspect local project tooling without running project code.",
    "map": "Usage: orbit map [SOURCE_DIRECTORY] [--git] [--needs] [--json]\nMap project tooling, cached Git state, and detected stacks.",
    "projects": "Usage: orbit projects [--json]\nInventory project manifest filenames without opening their contents.",
}


def _error(command: str, message: str, json_output: bool, code: int = 2) -> int:
    if json_output:
        render(Report(command=command, title=command.upper(), status="ERROR", summary=message,
                      next_action="Review the command and try again.", exit_code=code), json_output=True)
    else:
        print(f"orbit {command}: {message}", file=sys.stderr)
    return code


def main(arguments: list[str]) -> int:
    if not arguments or arguments[0] not in HELP:
        print("Usage: orbit {status|plan|enter|map|projects} [options]", file=sys.stderr)
        return 2
    command = arguments[0]
    options = arguments[1:]
    if options == ["--help"]:
        print(HELP[command])
        return 0
    json_output = False
    if "--json" in options:
        if options.count("--json") != 1:
            return _error(command, "--json may be specified once", True)
        options = [option for option in options if option != "--json"]
        json_output = True
    try:
        if command == "status":
            if options not in ([], ["--docker"]):
                return _error(command, HELP[command], json_output)
            result = doctor.build_report(ORBIT_ROOT, docker=bool(options))
        elif command == "projects":
            if options:
                return _error(command, HELP[command], json_output)
            result = inventory.build_report(workspace.default_source_root())
        elif command == "plan":
            details = "--details" in options
            if options.count("--details") > 1:
                return _error(command, "--details may be specified once", json_output)
            options = [option for option in options if option != "--details"]
            if len(options) % 2 != 0 or any(options[index] != "--profile" for index in range(0, len(options), 2)):
                return _error(command, HELP[command], json_output)
            result = plan.build_report(ORBIT_ROOT, options, details=details)
        elif command == "map":
            include_git = "--git" in options
            include_needs = "--needs" in options
            for flag in ("--git", "--needs"):
                if options.count(flag) > 1:
                    return _error(command, f"{flag} may be specified once", json_output)
            options = [option for option in options if option not in {"--git", "--needs"}]
            if len(options) > 1 or (options and options[0].startswith("-")):
                return _error(command, HELP[command], json_output)
            source = Path(options[0]).expanduser().resolve() if options else workspace.default_source_root()
            if not source.is_dir():
                return _error(command, f"no source directory at {source}", json_output)
            result = workspace.build_report(source, include_git=include_git, include_needs=include_needs)
        else:
            if len(options) > 1 or (options and options[0].startswith("-")):
                return _error(command, HELP[command], json_output)
            project = Path(options[0] if options else ".").expanduser().resolve()
            if not project.is_dir():
                return _error(command, f"no project directory at {project}", json_output)
            result = enter.build_report(project)
    except ProfileError as error:
        return _error(command, str(error), json_output)
    except plan.PlanError as error:
        return _error(command, str(error), json_output, code=1)
    except (enter.InputError, OSError, UnicodeError, RuntimeError) as error:
        return _error(command, str(error), json_output)
    render(result, json_output=json_output)
    return result.exit_code
