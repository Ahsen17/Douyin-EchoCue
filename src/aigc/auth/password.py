"""Password hashing tools for authentication.

This module provides the password hashing backend used by authentication flows.
It generates password hashes and verifies plain passwords against stored hashes.
"""

import base64
import hashlib
import hmac
import secrets

from advanced_alchemy.types.password_hash.base import HashingBackend
from sqlalchemy.sql.elements import BinaryExpression, ColumnElement

__all__ = ("PBKDF2Hasher",)


class PBKDF2Hasher(HashingBackend):
    """PBKDF2 password hashing backend."""

    algorithm = "pbkdf2_sha256"

    def __init__(self, iterations: int = 600_000, salt_bytes: int = 16) -> None:
        """Initialize the PBKDF2 hasher."""

        self.iterations = iterations
        self.salt_bytes = salt_bytes

    def hash(self, value: str | bytes) -> str:
        """Hash a plain password value."""

        salt = secrets.token_bytes(self.salt_bytes)
        digest = self._digest(value, salt, self.iterations)

        return "$".join(
            (
                self.algorithm,
                str(self.iterations),
                base64.b64encode(salt).decode("ascii"),
                base64.b64encode(digest).decode("ascii"),
            )
        )

    def verify(self, plain: str | bytes, hashed: str) -> bool:
        """Verify a plain password against a stored hash."""

        try:
            algorithm, iterations, salt, digest = hashed.split("$", 3)
        except ValueError:
            return False

        if algorithm != self.algorithm:
            return False

        try:
            iterations_int = int(iterations)
            salt_bytes = base64.b64decode(salt.encode("ascii"))
            digest_bytes = base64.b64decode(digest.encode("ascii"))
        except (ValueError, TypeError):
            return False

        return hmac.compare_digest(self._digest(plain, salt_bytes, iterations_int), digest_bytes)

    def needs_rehash(self, hashed: str) -> bool:
        """Return whether a stored hash should be regenerated."""

        try:
            algorithm, iterations, *_ = hashed.split("$", 3)
            iterations_int = int(iterations)
        except ValueError:
            return False

        return algorithm == self.algorithm and iterations_int < self.iterations

    def compare_expression(self, column: ColumnElement[str], plain: str | bytes) -> BinaryExpression[bool]:
        """Raise because PBKDF2 verification cannot be expressed as SQL."""

        msg = "PBKDF2Hasher does not support direct SQL comparison."
        raise NotImplementedError(msg)

    @staticmethod
    def _digest(value: str | bytes, salt: bytes, iterations: int) -> bytes:
        """Calculate a PBKDF2 digest."""

        return hashlib.pbkdf2_hmac("sha256", PBKDF2Hasher._ensure_bytes(value), salt, iterations)


password_hasher: HashingBackend = PBKDF2Hasher()
