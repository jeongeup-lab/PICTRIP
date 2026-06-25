"""Password hashing helpers (bcrypt).

Email/password is a secondary login path alongside OAuth (S09). Hashes are
stored in ``users.password_hash``.

We call the ``bcrypt`` package directly rather than through ``passlib`` because
the installed ``passlib==1.7.4`` cannot read ``bcrypt>=4.1``'s version metadata
and then raises on every hash (even short inputs). ``bcrypt`` is already a
declared dependency (pulled by the ``passlib[bcrypt]`` extra), so this adds no
new dependency. bcrypt enforces a hard 72-byte input limit, so we truncate the
UTF-8 encoded password to 72 bytes before hashing/verifying; the schema also
caps password length at 72.
"""

from __future__ import annotations

import bcrypt

_BCRYPT_MAX_BYTES = 72


def _truncate(raw: str) -> bytes:
    return raw.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(raw: str) -> str:
    """Return a bcrypt hash for ``raw`` (input truncated to bcrypt's 72-byte limit)."""
    return bcrypt.hashpw(_truncate(raw), bcrypt.gensalt()).decode("ascii")


def verify_password(raw: str, hashed: str | None) -> bool:
    """Verify ``raw`` against a stored hash. A missing/empty/malformed hash -> ``False``."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_truncate(raw), hashed.encode("ascii"))
    except ValueError:
        # Malformed/non-bcrypt stored hash — treat as a failed verification.
        return False
