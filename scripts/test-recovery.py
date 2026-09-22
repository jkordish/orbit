"""Check that recovery guidance uses names only and never mutates backups."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_MARKER = "RECOVERY_CONTENT_MUST_NOT_BE_PRINTED"


class RecoveryInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dev machine recovery ")
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(SOURCE_ROOT / "scripts/recovery", self.root / "scripts/recovery")
        shutil.copy2(SOURCE_ROOT / "scripts/env.sh", self.root / "scripts/env.sh")
        self.backups = self.root / ".state/backups"
        self.backups.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def run_report(self):
        return subprocess.run(
            ["bash", str(self.root / "scripts/recovery")],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_known_targets_are_actionable_without_reading_or_restoring_contents(self):
        snapshots = {
            "config.json.fixture": "docker config",
            "config.ghostty.fixture": "Ghostty user config",
            "finder.fixture.plist": "finder defaults",
            "global.fixture.plist": "global defaults",
            "ghostty.conf.fixture": "managed Ghostty fragment",
            "starship.toml.fixture": "Starship config",
            "zprofile.fixture": "zprofile",
            "zshrc.fixture": "zshrc",
            "gitconfig.fixture": "global git config",
        }
        for name, contents in snapshots.items():
            (self.backups / name).write_text(f"{PRIVATE_MARKER}: {contents}\n")
        (self.backups / "environments.fixture").mkdir()

        result = self.run_report()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "Filename-based target hints are not verified against saved contents.",
            result.stdout,
        )
        self.assertIn("Target hint: ~/.docker/config.json", result.stdout)
        self.assertIn(
            "Target hint: ~/Library/Application Support/com.mitchellh.ghostty/config.ghostty",
            result.stdout,
        )
        self.assertIn("Target hint: macOS Finder defaults (com.apple.finder)", result.stdout)
        self.assertIn("Target hint: macOS global defaults (NSGlobalDomain)", result.stdout)
        self.assertIn("Target hint: ~/.config/orbit/ghostty.conf", result.stdout)
        self.assertIn("Target hint: ~/.config/starship.toml", result.stdout)
        self.assertIn("Target hint: ~/.zprofile", result.stdout)
        self.assertIn("Target hint: ~/.zshrc", result.stdout)
        self.assertIn(
            "Target is ambiguous: ~/.gitconfig or ~/.config/orbit/gitconfig",
            result.stdout,
        )
        self.assertIn("lockfiles can rebuild these tools", result.stdout)
        self.assertNotIn(PRIVATE_MARKER, result.stdout)
        for name, contents in snapshots.items():
            self.assertEqual(
                (self.backups / name).read_text(), f"{PRIVATE_MARKER}: {contents}\n"
            )
        self.assertFalse((self.root / ".docker/config.json").exists())

    def test_unknown_items_and_symlinks_do_not_get_inferred_destinations(self):
        (self.backups / "mystery.snapshot").write_text(f"{PRIVATE_MARKER}\n")
        (self.root / "outside").write_text(f"{PRIVATE_MARKER}\n")
        (self.backups / "config.json.link").symlink_to(self.root / "outside")

        result = self.run_report()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Destination not inferred; inspect before restoring.", result.stdout)
        self.assertNotIn("Target hint: ~/.docker/config.json", result.stdout)
        self.assertNotIn(PRIVATE_MARKER, result.stdout)
        self.assertEqual((self.root / "outside").read_text(), f"{PRIVATE_MARKER}\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
