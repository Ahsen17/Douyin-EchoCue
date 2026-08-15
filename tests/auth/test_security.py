from aigc.auth.security import SESSION_EXCLUDE_PATHS, create_auth
from aigc.base import AuthConfig


class TestSessionAuth:
    def test_excludes_public_paths_from_auth_and_session_middleware(self) -> None:
        auth = create_auth(AuthConfig())
        expected_paths = list(SESSION_EXCLUDE_PATHS)

        assert auth.exclude == expected_paths
        assert auth.session_backend_config.exclude == expected_paths
