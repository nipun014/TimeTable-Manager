"""Password hashing and opaque session tokens. Stdlib only."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, HTTPException

from .db import db

COOKIE = "session"
SESSION_DAYS = 14
# n=2**14 needs 16 MB. Raising it without passing maxmem= trips OpenSSL's 32 MB
# default and raises ValueError, so leave these alone unless you set maxmem too.
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_pw(pw: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pw.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_pw(pw: str, stored: str) -> bool:
    try:
        _, salt, want = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, bytes.fromhex(want))


def start_session(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires.isoformat()),
    )
    return token


def set_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=SESSION_DAYS * 86400,
        secure=os.environ.get("HTTPS") == "1",
    )


def current_user(session: str | None = Cookie(default=None)) -> dict:
    """FastAPI dependency. 401 for a missing, unknown, or expired token."""
    if not session:
        raise HTTPException(401, "Not signed in")
    with db() as conn:
        row = conn.execute(
            "SELECT u.id, u.email, s.expires_at FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (session,),
        ).fetchone()
        if row is None:
            raise HTTPException(401, "Not signed in")
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE token = ?", (session,))
            raise HTTPException(401, "Session expired")
    return {"id": row["id"], "email": row["email"]}
