"""Protect local AI state while keeping shared assistant guidance trackable."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
IGNORED_PATHS = (
    ".agents/session.json",
    ".factory/session.json",
    ".junie/session.json",
    ".mcp.json",
    ".openhands/session.json",
    "src/.mcp.json",
    ".amazonq/session.json",
    ".augment/history/session.json",
    ".claude/projects/session.json",
    ".codex/sessions/session.json",
    ".copilot/session.json",
    ".continue/sessions/session.json",
    ".cursor/sessions/session.json",
    ".cursor/mcp.json",
    "src/.cursor/sessions/session.json",
    "src/.cursor/mcp.json",
    ".gemini/session.json",
    ".kilocode/session.json",
    ".opencode/session.json",
    ".roo/sessions/session.json",
    ".specstory/history/session.md",
    ".superpowers/specs/draft.md",
    ".trae/session.json",
    ".windsurf/sessions/session.json",
    "src/.windsurf/sessions/session.json",
    ".windsurf/rules/personal.md",
    ".aider.chat.history.md",
    "docs/superpowers/plans/draft.md",
    "src/AGENTS.local.md",
    "src/CLAUDE.local.md",
)

TRACKABLE_PATHS = (
    "AGENTS.md",
    "src/AGENTS.md",
    "CLAUDE.md",
    "src/CLAUDE.md",
    ".github/copilot-instructions.md",
    ".cursor/rules/project.mdc",
    "src/.cursor/rules/nested/project.mdc",
    ".cursor/commands/review.md",
    "src/.cursor/commands/nested/review.md",
    "src/.cursorrules",
    "src/.windsurfrules",
)


def is_ignored(repository, path):
    """Ask Git to evaluate the repository's actual ignore rules."""
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", path],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"git check-ignore failed for {path}: {result.stderr.strip()}"
        )
    return result.returncode == 0


class AIIgnorePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="dev machine ignore ")
        root = Path(cls.temporary.name)
        cls.repositories = []
        for name, source in (
            ("repository", SOURCE_ROOT / ".gitignore"),
            ("starter", SOURCE_ROOT / "templates/common/gitignore"),
        ):
            repository = root / name
            repository.mkdir()
            shutil.copy2(source, repository / ".gitignore")
            subprocess.run(
                ["git", "init", "--quiet", "--initial-branch=main"],
                cwd=repository,
                check=True,
            )
            cls.repositories.append(repository)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_local_assistant_state_and_generated_notes_are_ignored(self):
        for repository in self.repositories:
            for path in IGNORED_PATHS:
                with self.subTest(repository=repository.name, path=path):
                    self.assertTrue(
                        is_ignored(repository, path),
                        f"expected {path} to be ignored",
                    )

    def test_shared_assistant_guidance_and_configuration_are_trackable(self):
        for repository in self.repositories:
            for path in TRACKABLE_PATHS:
                with self.subTest(repository=repository.name, path=path):
                    self.assertFalse(
                        is_ignored(repository, path),
                        f"expected {path} to be trackable",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
