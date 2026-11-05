"""Build the release zip that judges and testers install from (3 Nov).

The zip is the committed tree (``git archive HEAD``: nothing local, no ``node_modules``) with
Dioscuri's README.md (GEMINI's own is README_GEMINI.md) and two kinds of files left out:
GEMINI's GIF animations and web-app assets, which Dioscuri does not use (80 MB), and caches.

Usage::

    python hackathon/scripts/make_release.py [--out DIR]

Writes ``DIR/dioscuri-<date>-<commit>.zip`` (default ``../release`` beside the repository) and
prints its size and file count. Commit first: uncommitted changes are not in it. Since 5 Nov
the app opens on an empty chat, so the recommended design's cache is no longer shipped.
"""

import argparse
import datetime as dt
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "dioscuri"
# Left out of the zip (prefixes of repository paths).
LEAVE_OUT = (
    "src/gemini_documentation/source/animations/",  # GIFs, 64 MB; the search reads the .rst
    "src/gemini_interface/static/",  # GEMINI's own web app, not used by Dioscuri
    ".github/",
    "docker-compose.yml",  # GEMINI's services; Dioscuri needs none of them
)
EXECUTABLE = ("install.sh", "start.sh", "uninstall.sh")


def git(*args: str) -> bytes:
    """Run git in the repository and return its output."""
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def build(out_dir: Path) -> Path:
    """Write the zip and return its path."""
    if git("status", "--porcelain", "--untracked-files=no").strip():
        print("Note: uncommitted changes are not in the zip (it is built from HEAD).")
    commit = git("rev-parse", "--short", "HEAD").decode().strip()
    stamp = dt.date.today().strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{NAME}-{stamp}-{commit}.zip"
    tar = tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", "HEAD")))
    files = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for member in tar.getmembers():
            if not member.isfile() or member.name.startswith(LEAVE_OUT):
                continue
            if "__pycache__" in member.name:
                continue
            data = tar.extractfile(member).read()
            z.writestr(_info(f"{NAME}/{member.name}", member), data)
            files += 1
    size = path.stat().st_size / 1e6
    print(f"{path}  {size:.1f} MB, {files} files, commit {commit}")
    return path


def _info(name: str, member: tarfile.TarInfo) -> zipfile.ZipInfo:
    """Return a zip entry that keeps the file's time and, for the scripts, its exec bit."""
    info = zipfile.ZipInfo(name, date_time=dt.datetime.fromtimestamp(member.mtime).timetuple()[:6])
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if name.endswith(EXECUTABLE) else 0o644
    info.external_attr = (0o100000 | mode) << 16
    return info


def main() -> None:
    """Parse the arguments and build the zip."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=ROOT.parent / "release")
    args = p.parse_args()
    build(args.out)


if __name__ == "__main__":
    sys.exit(main())
