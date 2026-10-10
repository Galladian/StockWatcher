"""Back up the database.

    python -m app.backup               write a timestamped copy into <data folder>/backups and keep the newest 14
    python -m app.backup --stdout      write one copy to standard output, to pull it off the server over SSH

Uses SQLite's own backup, so the copy is consistent even while the app is running.
"""
import argparse
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .config import DATA_DIR, DB_PATH

KEEP = 14


def snapshot(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(DB_PATH))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    dest.chmod(0o600)  # contains password hashes and portfolio data
    return dest


def prune(folder: Path, keep: int) -> list[Path]:
    old = sorted(folder.glob("stockwatcher-*.db"), reverse=True)[keep:]
    for f in old:
        f.unlink()
    return old


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stdout", action="store_true", help="write the copy to standard output")
    parser.add_argument("--keep", type=int, default=KEEP, help="how many backups to keep (default 14)")
    args = parser.parse_args()

    if args.stdout:
        with tempfile.TemporaryDirectory() as tmp:
            sys.stdout.buffer.write(snapshot(Path(tmp) / "copy.db").read_bytes())
        return
    folder = DATA_DIR / "backups"
    dest = snapshot(folder / f"stockwatcher-{datetime.now():%Y%m%d-%H%M%S}.db")
    removed = prune(folder, args.keep)
    print(f"Backed up to {dest} ({dest.stat().st_size:,} bytes). Removed {len(removed)} old backup(s).")


if __name__ == "__main__":
    main()
