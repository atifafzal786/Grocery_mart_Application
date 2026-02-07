from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from database import connect, setup_database

PBKDF2_ITERS = 210_000


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERS)


def ensure_default_admin() -> None:
    setup_database()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM users")
        if int(cur.fetchone()["c"]) > 0:
            return
        salt = os.urandom(16)
        pw_hash = _hash_password("admin", salt)
        cur.execute(
            "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
            ("admin", pw_hash, salt, "admin"),
        )
        conn.commit()


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str


def verify_credentials(username: str, password: str) -> AuthUser | None:
    ensure_default_admin()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT username, password_hash, salt, role FROM users WHERE username = ?",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        expected = row["password_hash"]
        actual = _hash_password(password, row["salt"])
        if not hmac.compare_digest(expected, actual):
            return None
        return AuthUser(username=row["username"], role=row["role"])


def change_password(username: str, new_password: str) -> None:
    salt = os.urandom(16)
    pw_hash = _hash_password(new_password, salt)
    with connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
            (pw_hash, salt, username),
        )
        conn.commit()

