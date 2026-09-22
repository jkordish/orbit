"""Install pinned Cargo utilities, preserving the five Homebrew-owned tools."""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
brew_owned = {"bat", "ripgrep", "starship", "git-delta", "just"}
cargo_bin = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))) / "bin"
entries = []
for line in (root / "config/cargo-tools.tsv").read_text().splitlines():
    if line.strip() and not line.startswith("#"):
        name, version, executable = line.split()
        if name not in brew_owned:
            entries.append((name, version, executable))

def installed_versions() -> dict[str, str]:
    result = subprocess.run(["cargo", "install", "--list"], check=True, capture_output=True, text=True)
    return dict(re.findall(r"^(\S+) v([^ :]+):$", result.stdout, re.MULTILINE))

installed = installed_versions()
pending = [(n, v, e) for n, v, e in entries if installed.get(n) != v or not os.access(cargo_bin / e, os.X_OK)]
if args.check:
    for name, version, _ in pending:
        print(f"MISSING/MISMATCH: {name} {version}")
    print(f"{len(entries) - len(pending)}/{len(entries)} pinned Cargo tools installed; five utilities remain Homebrew-owned.")
    raise SystemExit(bool(pending))

if not pending:
    print(f"All {len(entries)} pinned Cargo tools are already installed.")
    raise SystemExit(0)

backup_root = root / ".state/backups/cargo-tools"
if (root / ".state").is_symlink() or (root / ".state/backups").is_symlink() or backup_root.is_symlink():
    raise SystemExit("Refusing to use a symbolic-link backup path; inspect .state/backups first.")
for name, version, executable in pending:
    existing = cargo_bin / executable
    if not existing.is_file():
        continue
    digest = hashlib.sha256()
    with existing.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    digest_hex = digest.hexdigest()
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_root.chmod(0o700)
    already_saved = False
    for saved in backup_root.glob(f"{name}.*.bin"):
        if not saved.is_file():
            continue
        saved_digest = hashlib.sha256()
        with saved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                saved_digest.update(chunk)
        if saved_digest.hexdigest() == digest_hex:
            already_saved = True
            break
    if already_saved:
        continue
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    destination = backup_root / f"{name}.{version}.{stamp}.bin"
    shutil.copy2(existing, destination)
    print(f"Preserved existing executable before replacement: {existing}")

if installed.get("cargo-binstall") != "1.23.0" or not (cargo_bin / "cargo-binstall").exists():
    subprocess.run(["cargo", "+stable", "install", "cargo-binstall", "--version", "=1.23.0", "--locked", "--jobs", "6"], check=True)

# Install available prebuilt binaries first. Missing binary releases
# fall back to source builds below; both paths require the specified version.
specs = [f"{name}@={version}" for name, version, _ in pending if name != "cargo-binstall"]
if specs:
    subprocess.run([str(cargo_bin / "cargo-binstall"), "--no-confirm", "--locked", "--strategies", "crate-meta-data,quick-install", "--targets", "aarch64-apple-darwin", "--continue-on-failure", *specs], check=False)
installed = installed_versions()
failed = []
for name, version, executable in entries:
    if installed.get(name) == version and os.access(cargo_bin / executable, os.X_OK):
        continue
    print(f"Building {name} {version} from its locked source release", flush=True)
    result = subprocess.run(["cargo", "+stable", "install", name, "--version", f"={version}", "--locked", "--jobs", "6"], check=False)
    if result.returncode:
        failed.append(name)
if failed:
    raise SystemExit("Failed tools (rerun to retry): " + ", ".join(failed))
subprocess.run([os.sys.executable, str(Path(__file__)), "--check"], check=True)
