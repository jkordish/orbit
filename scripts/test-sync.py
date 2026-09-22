"""Exercise scripts/sync against disposable local Git repositories."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1]
TEST_IDENTITY = {
    "GIT_AUTHOR_NAME": "Sync Test",
    "GIT_AUTHOR_EMAIL": "sync-test@example.invalid",
    "GIT_COMMITTER_NAME": "Sync Test",
    "GIT_COMMITTER_EMAIL": "sync-test@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def git(repo, *args, check=True):
    """Run Git with an isolated identity and return its captured result."""
    environment = os.environ.copy()
    environment.update(TEST_IDENTITY)
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed ({result.returncode}):\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dev machine sync ")
        self.root = Path(self.temporary.name)
        self.seed = self.root / "seed"
        self.origin = self.root / "origin.git"
        self.checkout = self.root / "working clone with spaces"
        self.seed.mkdir()

        git(None, "init", "--initial-branch=main", str(self.seed))
        shutil.copy2(SOURCE_ROOT / ".gitignore", self.seed / ".gitignore")
        (self.seed / "tracked.txt").write_text("initial\n")
        git(self.seed, "add", ".gitignore", "tracked.txt")
        git(self.seed, "commit", "-m", "initial fixture commit")
        git(None, "clone", "--bare", str(self.seed), str(self.origin))
        git(self.seed, "remote", "add", "origin", str(self.origin))
        git(None, "clone", "--branch", "main", str(self.origin), str(self.checkout))
        git(self.checkout, "config", "user.name", "Sync Test")
        git(self.checkout, "config", "user.email", "sync-test@example.invalid")

        scripts = self.checkout / "scripts"
        scripts.mkdir()
        shutil.copy2(SOURCE_ROOT / "scripts/env.sh", scripts / "env.sh")
        source_sync = SOURCE_ROOT / "scripts/sync"
        if source_sync.exists():
            shutil.copy2(source_sync, scripts / "sync")
        git(self.checkout, "add", "scripts/env.sh")
        if source_sync.exists():
            git(self.checkout, "add", "scripts/sync")
        git(self.checkout, "commit", "-m", "add sync command under test")
        git(self.checkout, "push", "origin", "main")
        git(self.seed, "pull", "--ff-only", "origin", "main")

    def tearDown(self):
        self.temporary.cleanup()

    def run_sync(self, *args):
        environment = os.environ.copy()
        environment.update(TEST_IDENTITY)
        return subprocess.run(
            ["/bin/bash", str(self.checkout / "scripts/sync"), *args],
            cwd=self.checkout,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def sha(self, repo, revision):
        return git(repo, "rev-parse", revision).stdout.strip()

    def remote_sha(self):
        return git(None, "--git-dir", str(self.origin), "rev-parse", "refs/heads/main").stdout.strip()

    def branch(self):
        return git(self.checkout, "branch", "--show-current").stdout.strip()

    def status(self):
        return git(
            self.checkout,
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--ignore-submodules=none",
        ).stdout

    def assert_cli_error(self, result, fragment):
        combined = (result.stdout + result.stderr).lower()
        self.assertNotIn("no such file or directory", combined)
        self.assertIn(fragment.lower(), combined)

    def commit_file(self, repo, text, message):
        (Path(repo) / "tracked.txt").write_text(text)
        git(repo, "add", "tracked.txt")
        git(repo, "commit", "-m", message)
        return self.sha(repo, "HEAD")

    def push_remote_change(self, text, message):
        self.commit_file(self.seed, text, message)
        git(self.seed, "push", "origin", "main")
        return self.sha(self.seed, "HEAD")

    def push_ignored_backup_path(self, contents, message):
        path = self.seed / ".state/backups/sentinel"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        git(self.seed, "add", "-f", ".state/backups/sentinel")
        git(self.seed, "commit", "-m", message)
        git(self.seed, "push", "origin", "main")
        return self.sha(self.seed, "HEAD")

    def test_clean_main_matches_remote(self):
        expected = self.remote_sha()
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ORBIT / REPOSITORY SYNC", result.stdout)
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.status(), "")
        self.assertEqual(self.sha(self.checkout, "HEAD"), expected)

    def test_fast_forwards_to_new_remote_commit(self):
        expected = self.push_remote_change("from remote\n", "advance remote main")
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.sha(self.checkout, "HEAD"), expected)
        self.assertEqual(self.sha(self.checkout, "origin/main"), expected)
        self.assertEqual((self.checkout / "tracked.txt").read_text(), "from remote\n")

    def test_uses_validated_remote_sha_when_local_tag_shadows_origin_main(self):
        git(self.checkout, "switch", "-c", "codex/keep-me")
        feature_sha = self.commit_file(self.checkout, "unpublished feature\n", "unpublished feature")
        git(self.checkout, "tag", "origin/main", feature_sha)
        git(self.checkout, "switch", "main")
        expected = self.remote_sha()

        result = self.run_sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "HEAD"), expected)
        self.assertEqual(self.sha(self.checkout, "refs/remotes/origin/main"), expected)
        self.assertEqual(self.sha(self.checkout, "refs/tags/origin/main"), feature_sha)
        self.assertEqual(self.sha(self.checkout, "codex/keep-me"), feature_sha)

    def test_refuses_ignored_backup_collision_when_switching_to_existing_main(self):
        git(self.checkout, "switch", "-c", "codex/current")
        current_sha = self.sha(self.checkout, "HEAD")
        git(self.checkout, "branch", "-D", "main")
        remote_sha = self.push_ignored_backup_path(b"remote tracked bytes\0\n", "track backup path")
        git(self.checkout, "fetch", "origin")
        git(self.checkout, "branch", "main", remote_sha)
        path = self.checkout / ".state/backups/sentinel"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"local ignored backup bytes\0\n")
        self.assertEqual(self.status(), "")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), b"local ignored backup bytes\0\n")
        self.assertEqual(self.branch(), "codex/current")
        self.assertEqual(self.sha(self.checkout, "main"), remote_sha)
        self.assertEqual(self.sha(self.checkout, "codex/current"), current_sha)
        self.assertEqual(self.sha(self.checkout, "refs/remotes/origin/main"), remote_sha)
        self.assertEqual(self.status(), "")

    def test_refuses_ignored_backup_collision_when_creating_missing_main(self):
        git(self.checkout, "switch", "-c", "codex/current")
        current_sha = self.sha(self.checkout, "HEAD")
        git(self.checkout, "branch", "-D", "main")
        remote_sha = self.push_ignored_backup_path(b"remote tracked bytes\0\n", "track backup path")
        path = self.checkout / ".state/backups/sentinel"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"local ignored backup bytes\0\n")
        self.assertEqual(self.status(), "")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), b"local ignored backup bytes\0\n")
        self.assertEqual(self.branch(), "codex/current")
        self.assertEqual(self.sha(self.checkout, "codex/current"), current_sha)
        self.assertNotEqual(
            git(self.checkout, "show-ref", "--verify", "--hash", "refs/heads/main", check=False).returncode,
            0,
        )
        self.assertEqual(self.sha(self.checkout, "refs/remotes/origin/main"), remote_sha)
        self.assertEqual(self.status(), "")

    def test_refuses_ignored_backup_collision_during_fast_forward(self):
        remote_sha = self.push_ignored_backup_path(b"remote tracked bytes\0\n", "track backup path")
        path = self.checkout / ".state/backups/sentinel"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"local ignored backup bytes\0\n")
        main_sha = self.sha(self.checkout, "main")
        self.assertEqual(self.status(), "")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), b"local ignored backup bytes\0\n")
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "main"), main_sha)
        self.assertEqual(self.sha(self.checkout, "refs/remotes/origin/main"), remote_sha)
        self.assertEqual(self.status(), "")

    def test_creates_missing_local_main_from_origin(self):
        git(self.checkout, "switch", "-c", "codex/keep-me")
        git(self.checkout, "branch", "-D", "main")
        expected = self.remote_sha()

        result = self.run_sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "HEAD"), expected)
        self.assertEqual(
            git(self.checkout, "rev-parse", "--abbrev-ref", "main@{upstream}").stdout.strip(),
            "origin/main",
        )
        self.assertEqual(self.sha(self.checkout, "codex/keep-me"), expected)

    def test_preserves_named_feature_branch(self):
        git(self.checkout, "switch", "-c", "codex/keep-me")
        feature_sha = self.commit_file(self.checkout, "local feature\n", "local feature")

        result = self.run_sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "codex/keep-me"), feature_sha)
        self.assertEqual(self.sha(self.checkout, "HEAD"), self.sha(self.checkout, "origin/main"))
        self.assertIn("codex/keep-me", result.stdout)

    def test_rescues_detached_head_before_switching(self):
        git(self.checkout, "switch", "-c", "codex/detached-work")
        detached_sha = self.commit_file(self.checkout, "detached work\n", "detached work")
        git(self.checkout, "switch", "--detach", detached_sha)

        result = self.run_sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "HEAD"), self.sha(self.checkout, "origin/main"))
        rescue_refs = git(
            self.checkout,
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads/rescue/",
        ).stdout.splitlines()
        matching = [ref for ref in rescue_refs if self.sha(self.checkout, ref) == detached_sha]
        self.assertEqual(len(matching), 1, rescue_refs)
        self.assertIn(matching[0], result.stdout)

    def test_refuses_modified_tracked_file_without_changes(self):
        path = self.checkout / "tracked.txt"
        path.write_text("preserve modified bytes\n")
        before_bytes = path.read_bytes()
        before_status = self.status()
        before_branch = self.branch()

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "working tree")
        self.assertEqual(path.read_bytes(), before_bytes)
        self.assertEqual(self.status(), before_status)
        self.assertEqual(self.branch(), before_branch)

    def test_refuses_staged_file_without_changes(self):
        path = self.checkout / "tracked.txt"
        path.write_text("preserve staged bytes\n")
        git(self.checkout, "add", "tracked.txt")
        before_bytes = path.read_bytes()
        before_status = self.status()
        before_branch = self.branch()
        before_index = git(self.checkout, "write-tree").stdout.strip()

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "working tree")
        self.assertEqual(path.read_bytes(), before_bytes)
        self.assertEqual(self.status(), before_status)
        self.assertEqual(git(self.checkout, "write-tree").stdout.strip(), before_index)
        self.assertEqual(self.branch(), before_branch)

    def test_refuses_untracked_file_without_changes(self):
        path = self.checkout / "untracked sentinel.txt"
        path.write_text("preserve untracked bytes\n")
        before_bytes = path.read_bytes()
        before_status = self.status()
        before_branch = self.branch()

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "working tree")
        self.assertEqual(path.read_bytes(), before_bytes)
        self.assertEqual(self.status(), before_status)
        self.assertEqual(self.branch(), before_branch)

    def test_refuses_conflicted_worktree_without_changes(self):
        git(self.checkout, "switch", "-c", "codex/conflict")
        self.commit_file(self.checkout, "feature version\n", "feature version")
        git(self.checkout, "switch", "main")
        self.commit_file(self.checkout, "main version\n", "main version")
        merge = git(self.checkout, "merge", "codex/conflict", check=False)
        self.assertNotEqual(merge.returncode, 0)
        path = self.checkout / "tracked.txt"
        before_bytes = path.read_bytes()
        before_status = self.status()
        before_branch = self.branch()

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "working tree")
        self.assertEqual(path.read_bytes(), before_bytes)
        self.assertEqual(self.status(), before_status)
        self.assertEqual(self.branch(), before_branch)

    def test_refuses_local_main_ahead_before_switching_feature(self):
        self.commit_file(self.checkout, "local main only\n", "local main only")
        main_sha = self.sha(self.checkout, "main")
        git(self.checkout, "switch", "-c", "codex/current")
        current_sha = self.sha(self.checkout, "HEAD")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "local main")
        self.assertEqual(self.branch(), "codex/current")
        self.assertEqual(self.sha(self.checkout, "main"), main_sha)
        self.assertEqual(self.sha(self.checkout, "codex/current"), current_sha)

    def test_refuses_diverged_main_before_switching_feature(self):
        local_main_sha = self.commit_file(self.checkout, "local version\n", "local version")
        remote_sha = self.push_remote_change("remote version\n", "remote version")
        git(self.checkout, "switch", "-c", "codex/current")
        current_sha = self.sha(self.checkout, "HEAD")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "local main")
        self.assertEqual(self.branch(), "codex/current")
        self.assertEqual(self.sha(self.checkout, "main"), local_main_sha)
        self.assertEqual(self.sha(self.checkout, "codex/current"), current_sha)
        self.assertEqual(self.sha(self.checkout, "origin/main"), remote_sha)

    def test_refuses_when_origin_is_missing(self):
        git(self.checkout, "remote", "remove", "origin")
        before_sha = self.sha(self.checkout, "HEAD")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "origin")
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "HEAD"), before_sha)

    def test_refuses_when_remote_main_is_missing(self):
        git(None, "--git-dir", str(self.origin), "update-ref", "-d", "refs/heads/main")
        before_sha = self.sha(self.checkout, "HEAD")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("no such file or directory", (result.stdout + result.stderr).lower())
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "HEAD"), before_sha)

    def test_refuses_non_fast_forward_remote_tracking_update(self):
        rewrite = self.root / "unrelated remote history"
        rewrite.mkdir()
        git(None, "init", "--initial-branch=main", str(rewrite))
        (rewrite / "other.txt").write_text("unrelated root\n")
        git(rewrite, "add", "other.txt")
        git(rewrite, "commit", "-m", "unrelated remote root")
        rewritten_sha = self.sha(rewrite, "HEAD")
        original_remote_tracking_sha = self.sha(self.checkout, "origin/main")
        git(rewrite, "remote", "add", "origin", str(self.origin))
        git(rewrite, "push", "--force", "origin", "main")
        before_sha = self.sha(self.checkout, "HEAD")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("no such file or directory", (result.stdout + result.stderr).lower())
        self.assertEqual(self.branch(), "main")
        self.assertEqual(self.sha(self.checkout, "HEAD"), before_sha)
        self.assertEqual(self.sha(self.checkout, "origin/main"), original_remote_tracking_sha)

    def test_refuses_if_main_is_checked_out_in_another_worktree(self):
        git(self.checkout, "switch", "-c", "codex/current")
        second_worktree = self.root / "second worktree"
        git(self.checkout, "worktree", "add", str(second_worktree), "main")
        current_sha = self.sha(self.checkout, "HEAD")

        result = self.run_sync()

        self.assertNotEqual(result.returncode, 0)
        self.assert_cli_error(result, "worktree")
        self.assertEqual(self.branch(), "codex/current")
        self.assertEqual(self.sha(self.checkout, "HEAD"), current_sha)
        self.assertEqual(
            git(second_worktree, "branch", "--show-current").stdout.strip(),
            "main",
        )

    def test_preserves_ignored_local_backup_bytes(self):
        path = self.checkout / ".state/backups/sentinel"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"local backup must remain untouched\0\n")

        result = self.run_sync()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), b"local backup must remain untouched\0\n")
        self.assertEqual(self.status(), "")

    def test_help_and_invalid_arguments(self):
        help_result = self.run_sync("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stdout + help_result.stderr)
        self.assertIn("origin/main", help_result.stdout)

        invalid_result = self.run_sync("--force")
        self.assertEqual(invalid_result.returncode, 2)
        self.assertIn("Usage:", invalid_result.stderr)


if __name__ == "__main__":
    unittest.main()
