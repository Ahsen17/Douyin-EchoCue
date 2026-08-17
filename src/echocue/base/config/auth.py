from datetime import timedelta
from typing import Literal

from echocue.base.schema import BaseStruct

__all__ = ("AuthConfig",)


class AuthConfig(BaseStruct):
    """Authentication configuration."""

    session_cookie_key: str = "session"
    session_max_age_seconds: int = 3600
    session_renew_on_access: bool = True
    session_store_name: str = "sessions"
    session_store_namespace: str = "ECHOCUE_SESSIONS"
    session_cookie_secure: bool = False
    session_cookie_httponly: bool = True
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    @property
    def session_max_age(self) -> timedelta:
        """Return the session max age as a timedelta."""

        return timedelta(seconds=self.session_max_age_seconds)
