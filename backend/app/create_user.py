"""Create a user, or reset an existing user's password.

Run from the backend folder:   python -m app.create_user <username>
"""
import re
import sys
from getpass import getpass

from sqlalchemy import select

from .db import SessionLocal, init_db
from .models import User
from .security import hash_password


def main() -> None:
    username = (sys.argv[1] if len(sys.argv) > 1 else input("Username: ")).strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{3,50}", username):
        sys.exit("Username must be 3-50 characters: letters, numbers, dots, dashes, underscores.")

    password = getpass("Password (min 10 characters): ")
    if len(password) < 10:
        sys.exit("Password must be at least 10 characters.")
    if getpass("Repeat password: ") != password:
        sys.exit("Passwords didn't match.")

    init_db()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user:
            user.password_hash = hash_password(password)
            print(f"Updated password for '{username}'.")
        else:
            db.add(User(username=username, password_hash=hash_password(password)))
            print(f"Created user '{username}'.")
        db.commit()


if __name__ == "__main__":
    main()
