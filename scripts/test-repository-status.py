"""Check that repository readiness is read-only and makes sync risks visible."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
STATUS_COMMAND = SOURCE_ROOT / "scripts" / "repository-status"
TEST_IDENTITY = {
    "GIT_AUTHOR_NAME": "Repository Status Test",
    "GIT_AUTHOR_EMAIL": "repo-status@example.invalid",
    "GIT_COMMITTER_NAME": "Repository Status Test",
    "GIT_COMMITTER_EMAIL": "repo-status@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def git(repository, *arguments, check=True):
    environment = os.environ.copy()
    environment.update(TEST_IDENTITY)
    command = ["git"]
    if repository is not None:
        command.extend(("-C", str(repository)))
    command.extend(arguments)
    result = subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"{' '.join(command)} failed ({result.returncode}):\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


class RepositoryStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dev machine status ")
        self.root = Path(self.temporary.name)
        self.seed = self.root / "seed"
        self.origin = self.root / "origin.git"
        self.checkout = self.root / "working clone"
        self.writer = self.root / "remote writer"
        self.seed.mkdir()
        git(None, "init", "--initial-branch=main", str(self.seed))
        (self.seed / "tracked.txt").write_text("initial\n")
        git(self.seed, "add", "tracked.txt")
        git(self.seed, "commit", "-m", "initial")
        git(None, "clone", "--bare", str(self.seed), str(self.origin))
        git(None, "clone", str(self.origin), str(self.checkout))
        git(self.checkout, "config", "user.name", "Repository Status Test")
        git(self.checkout, "config", "user.email", "repo-status@example.invalid")
        git(None, "clone", str(self.origin), str(self.writer))
        git(self.writer, "config", "user.name", "Repository Status Test")
        git(self.writer, "config", "user.email", "repo-status@example.invalid")

    def tearDown(self):
        self.temporary.cleanup()

    def status(self, repository=None):
        path = repository or self.checkout
        result = subprocess.run(
            [str(STATUS_COMMAND), str(path)],
            env={**os.environ, **TEST_IDENTITY},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fields = result.stdout.rstrip("\n").split("\t")
        self.assertEqual(len(fields), 3, result.stdout)
        return fields

    def push_remote_commit(self, contents, message):
        (self.writer / "tracked.txt").write_text(contents)
        git(self.writer, "add", "tracked.txt")
        git(self.writer, "commit", "-m", message)
        git(self.writer, "push", "origin", "main")

    def test_clean_main_matches_the_cached_origin_main_ref(self):
        state, detail, action = self.status()
        self.assertEqual(state, "SYNCED")
        self.assertEqual(detail, "main = origin/main")
        self.assertEqual(action, "")

    def test_dirty_working_tree_is_reported_without_exposing_paths(self):
        (self.checkout / "tracked.txt").write_text("changed\n")
        (self.checkout / "private filename.txt").write_text("local data\n")

        state, detail, action = self.status()

        self.assertEqual(state, "DIRTY")
        self.assertEqual(detail, "2 local paths")
        self.assertIn("preserve", action.lower())
        self.assertNotIn("private filename", action)

    def test_behind_main_is_reported_as_fast_forwardable(self):
        self.push_remote_commit("remote change\n", "advance remote main")
        git(self.checkout, "fetch", "origin")

        state, detail, action = self.status()

        self.assertEqual(state, "BEHIND")
        self.assertEqual(detail, "1 commit behind")
        self.assertIn("fast-forward this checkout", action)
        self.assertNotIn("scripts/sync", action)

    def test_local_commit_ahead_of_main_is_not_advised_to_sync(self):
        (self.checkout / "tracked.txt").write_text("local change\n")
        git(self.checkout, "add", "tracked.txt")
        git(self.checkout, "commit", "-m", "local only")

        state, detail, action = self.status()

        self.assertEqual(state, "AHEAD")
        self.assertEqual(detail, "1 local commit")
        self.assertIn("review", action.lower())
        self.assertNotIn("Run './scripts/sync'", action)

    def test_diverged_main_requires_review(self):
        (self.checkout / "tracked.txt").write_text("local change\n")
        git(self.checkout, "add", "tracked.txt")
        git(self.checkout, "commit", "-m", "local only")
        self.push_remote_commit("remote change\n", "remote only")
        git(self.checkout, "fetch", "origin")

        state, detail, action = self.status()

        self.assertEqual(state, "DIVERGED")
        self.assertEqual(detail, "1 ahead, 1 behind")
        self.assertIn("review", action.lower())
        self.assertNotIn("Run './scripts/sync'", action)

    def test_clean_feature_branch_is_reported_without_changing_branches(self):
        git(self.checkout, "switch", "-c", "codex/example")
        before = git(self.checkout, "branch", "--show-current").stdout.strip()

        state, detail, action = self.status()

        self.assertEqual(state, "OFF MAIN")
        self.assertEqual(detail, "branch codex/example")
        self.assertIn("switching branches in this checkout", action)
        self.assertNotIn("scripts/sync", action)
        self.assertEqual(git(self.checkout, "branch", "--show-current").stdout.strip(), before)

    def test_detached_head_is_reported(self):
        git(self.checkout, "checkout", "--detach", "HEAD")

        state, detail, action = self.status()

        self.assertEqual(state, "DETACHED")
        self.assertEqual(detail, "detached HEAD")
        self.assertIn("current commit", action)
        self.assertNotIn("scripts/sync", action)

    def test_missing_cached_origin_main_is_reported_without_fetching(self):
        git(self.checkout, "update-ref", "-d", "refs/remotes/origin/main")

        state, detail, action = self.status()

        self.assertEqual(state, "NO REMOTE REF")
        self.assertEqual(detail, "origin/main unavailable")
        self.assertIn("origin/main", action)
        self.assertNotIn("scripts/sync", action)
        self.assertNotEqual(
            git(self.checkout, "show-ref", "--verify", "refs/remotes/origin/main", check=False).returncode,
            0,
        )

    def test_non_repository_is_reported(self):
        empty = self.root / "not a repository"
        empty.mkdir()

        state, detail, action = self.status(empty)

        self.assertEqual(state, "NOT REPOSITORY")
        self.assertEqual(detail, "Git checkout unavailable")
        self.assertEqual(action, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
