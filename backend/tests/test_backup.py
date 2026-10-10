import sqlite3

from app import backup


def test_backup_is_a_complete_private_copy(make_user, tmp_path):
    name = make_user("backup")
    dest = backup.snapshot(tmp_path / "copy.db")
    assert oct(dest.stat().st_mode & 0o777) == "0o600"
    con = sqlite3.connect(dest)
    try:
        assert con.execute("SELECT COUNT(*) FROM users WHERE username = ?", (name,)).fetchone()[0] == 1
    finally:
        con.close()


def test_only_the_newest_backups_are_kept(tmp_path):
    for day in range(1, 21):
        (tmp_path / f"stockwatcher-202601{day:02d}-030000.db").write_bytes(b"x")
    (tmp_path / "unrelated.txt").write_text("keep me")
    removed = backup.prune(tmp_path, keep=14)
    left = sorted(p.name for p in tmp_path.glob("stockwatcher-*.db"))
    assert len(removed) == 6 and len(left) == 14 and left[0].startswith("stockwatcher-20260107")
    assert (tmp_path / "unrelated.txt").exists()
