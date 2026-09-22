"""Protect the project starter command's public workflow."""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMMAND = REPOSITORY_ROOT / "scripts" / "new-project"
MODULE_SPEC = importlib.util.spec_from_file_location(
    "new_project", REPOSITORY_ROOT / "scripts" / "new_project.py"
)
NEW_PROJECT = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(NEW_PROJECT)


class ProjectStarterTests(unittest.TestCase):
    def test_project_creation_command_is_available(self):
        self.assertTrue(COMMAND.is_file(), "scripts/new-project must be installed")
        self.assertTrue(COMMAND.stat().st_mode & 0o111, "scripts/new-project must be executable")

    def test_lists_every_supported_starter(self):
        result = subprocess.run(
            [str(COMMAND), "--list"],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for template in ("python", "typescript", "go", "rust", "nix"):
            self.assertIn(template, result.stdout)

    def test_creates_python_project_with_locked_identity_and_shared_guidance(self):
        with tempfile.TemporaryDirectory(prefix="dev machine starter ") as directory:
            parent = Path(directory)
            name = "morning-brief"
            result = self.run_create(parent, "python", name)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            project = parent / name
            self.assertIn(
                f"cd '{project.resolve()}' && git init --initial-branch=main",
                result.stdout,
            )
            self.assertIn('name = "morning-brief"', (project / "pyproject.toml").read_text())
            self.assertIn('name = "morning-brief"', (project / "uv.lock").read_text())
            self.assertIn("# morning-brief", (project / "README.md").read_text())
            self.assertTrue((project / "AGENTS.md").is_file())
            self.assertTrue((project / ".gitignore").is_file())
            self.assertFalse((project / ".git").exists())

            subprocess.run(
                ["git", "init", "--quiet", "--initial-branch=main"],
                cwd=project,
                check=True,
            )
            ignored_paths = (
                ".agents/session.json",
                ".amazonq/session.json",
                ".augment/session.json",
                ".claude/projects/session.json",
                ".codex/sessions/session.json",
                ".copilot/session.json",
                ".continue/session.json",
                ".cursor/session.json",
                ".gemini/session.json",
                ".kilocode/session.json",
                ".opencode/session.json",
                ".roo/session.json",
                ".specstory/session.json",
                ".superpowers/session.json",
                ".trae/session.json",
                ".windsurf/session.json",
                ".aider.chat.history.md",
                "AGENTS.local.md",
                "CLAUDE.local.md",
                "docs/superpowers/plans/draft.md",
            )
            for path in ignored_paths:
                with self.subTest(ignored_path=path):
                    self.assertTrue(self.is_ignored(project, path), path)
            self.assertFalse(self.is_ignored(project, "AGENTS.md"))
            self.assertFalse(self.is_ignored(project, "CLAUDE.md"))
            self.assertFalse(self.is_ignored(project, ".github/copilot-instructions.md"))

    def test_git_option_initializes_an_empty_main_repository(self):
        with tempfile.TemporaryDirectory(prefix="dev machine starter ") as directory:
            parent = Path(directory)
            result = self.run_create(parent, "python", "ready-repo", "--git")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            project = parent / "ready-repo"
            branch = subprocess.run(
                ["git", "-C", str(project), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            head = subprocess.run(
                ["git", "-C", str(project), "rev-parse", "--verify", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            remotes = subprocess.run(
                ["git", "-C", str(project), "remote"],
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertEqual(branch.stdout.strip(), "main")
            self.assertNotEqual(head.returncode, 0, "starter initialization must not commit")
            self.assertEqual(remotes.stdout, "", "starter initialization must not configure a remote")

    def test_git_init_failure_does_not_publish_a_partial_project(self):
        with tempfile.TemporaryDirectory(prefix="dev machine starter ") as directory:
            parent = Path(directory)
            fake_bin = parent / "fake-bin"
            fake_bin.mkdir()
            fake_git = fake_bin / "git"
            fake_git.write_text("#!/bin/sh\nprintf 'simulated git init failure\\n' >&2\nexit 1\n")
            fake_git.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"

            result = subprocess.run(
                [str(COMMAND), "python", "partial-repo", str(parent), "--git"],
                cwd=REPOSITORY_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("could not initialize Git repository", result.stderr)
            self.assertFalse((parent / "partial-repo").exists())
            self.assertEqual(list(parent.glob(".partial-repo.staging-*")), [])

    def test_updates_names_in_each_language_manifest_and_lock(self):
        cases = {
            "typescript": (
                ("package.json", "typescript-starter", "sample-project"),
            ),
            "go": (
                ("go.mod", "example.com/go-starter", "example.com/sample-project"),
            ),
            "rust": (
                ("Cargo.toml", 'name = "rust-starter"', 'name = "sample-project"'),
                ("Cargo.lock", 'name = "rust-starter"', 'name = "sample-project"'),
            ),
        }
        with tempfile.TemporaryDirectory(prefix="dev machine starter ") as directory:
            parent = Path(directory)
            for template, manifests in cases.items():
                with self.subTest(template=template):
                    result = self.run_create(parent, template, "sample-project")
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    for manifest, old, new in manifests:
                        with self.subTest(manifest=manifest):
                            contents = (parent / "sample-project" / manifest).read_text()
                            self.assertIn(new, contents)
                            self.assertNotIn(old, contents)
                    shutil.rmtree(parent / "sample-project")

    def test_creates_nix_starter_with_review_and_lock_guidance(self):
        with tempfile.TemporaryDirectory(prefix="dev machine starter ") as directory:
            parent = Path(directory)
            result = self.run_create(parent, "nix", "native-tools")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            project = parent / "native-tools"
            self.assertTrue((project / "flake.nix").is_file())
            self.assertTrue((project / ".envrc").is_file())
            readme = (project / "README.md").read_text()
            self.assertIn("# native-tools", readme)
            self.assertIn("nix flake lock", readme)
            self.assertNotIn("{{project_name}}", readme)

    def test_refuses_existing_destination_without_changing_it(self):
        with tempfile.TemporaryDirectory(prefix="dev machine starter ") as directory:
            parent = Path(directory)
            project = parent / "do-not-touch"
            project.mkdir()
            sentinel = project / "sentinel.txt"
            sentinel.write_text("user data\n")

            result = self.run_create(parent, "python", "do-not-touch")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already exists", result.stderr)
            self.assertEqual(sentinel.read_text(), "user data\n")
            self.assertEqual(list(parent.glob(".do-not-touch.staging-*")), [])

    def test_rejects_invalid_name_and_missing_parent_before_writing(self):
        with tempfile.TemporaryDirectory(prefix="dev machine starter ") as directory:
            parent = Path(directory)
            invalid = self.run_create(parent, "python", "../escape")
            missing = self.run_create(parent / "missing", "python", "valid-name")
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("lowercase", invalid.stderr)
            self.assertFalse((parent.parent / "escape").exists())
            self.assertNotEqual(missing.returncode, 0)
            self.assertFalse((parent / "missing").exists())

    def test_copy_excludes_generated_environment_directories(self):
        with tempfile.TemporaryDirectory(prefix="dev machine template ") as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            source.mkdir()
            (source / "main.py").write_text("print('keep')\n")
            for generated in (".venv", "__pycache__", ".pytest_cache", "node_modules", "target"):
                (source / generated).mkdir()
                (source / generated / "payload").write_text("discard\n")

            NEW_PROJECT.copy_template(source, destination)

            self.assertEqual((destination / "main.py").read_text(), "print('keep')\n")
            for generated in (".venv", "__pycache__", ".pytest_cache", "node_modules", "target"):
                with self.subTest(generated=generated):
                    self.assertFalse((destination / generated).exists())

    def run_create(self, parent, template, name, *options):
        return subprocess.run(
            [str(COMMAND), template, name, str(parent), *options],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def is_ignored(self, repository, path):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", path],
            cwd=repository,
            check=False,
        )
        self.assertIn(result.returncode, (0, 1))
        return result.returncode == 0


if __name__ == "__main__":
    unittest.main(verbosity=2)
