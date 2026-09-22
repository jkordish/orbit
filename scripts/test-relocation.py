"""Verify that relocation invalidates generated environments without losing their data."""
import shutil
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).resolve().parent
generated = ["templates/python/.venv", "templates/typescript/node_modules", "templates/rust/target"]

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary) / "original repo"
    (root / "scripts").mkdir(parents=True)
    for name in ["env.sh", "prepare-environments"]:
        shutil.copy2(source / name, root / "scripts" / name)
    for path in generated:
        directory = root / path
        directory.mkdir(parents=True)
        (directory / "sentinel").write_text("preserve me")

    def prepare(repo: Path) -> None:
        subprocess.run(["/bin/bash", str(repo / "scripts/prepare-environments")], check=True)

    prepare(root)
    assert all(not (root / p).exists() for p in generated)
    assert len(list((root / ".state/backups").rglob("sentinel"))) == 3
    assert (root / ".state/environment-root").read_text().strip() == str(root.resolve())
    for path in generated:
        (root / path).mkdir(parents=True)
        (root / path / "sentinel").write_text("rebuilt here")
    prepare(root)
    assert all((root / p / "sentinel").read_text() == "rebuilt here" for p in generated)

    moved = Path(temporary) / "copied repo"
    shutil.copytree(root, moved, symlinks=False)
    prepare(moved)
    assert all(not (moved / p).exists() for p in generated)
    assert all((root / p / "sentinel").exists() for p in generated)
    assert len(list((moved / ".state/backups").rglob("sentinel"))) == 6
print("Relocation, data preservation, paths with spaces, and repeat application passed.")
