from pathlib import Path

import pytest
from pytest import MonkeyPatch

from echocue.base import Config


class TestConfig:
    def test_remediation_token_defaults_to_fifteen_minutes(self) -> None:
        assert Config().client.remediation_token_ttl_seconds == 900

    def test_room_status_cache_defaults_to_two_hours(self) -> None:
        assert Config().live.room_status_cache_ttl_seconds == 7_200

    def test_loads_default_yaml_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
app:
  host: "127.0.0.1"
  port: 9000
alchemy:
  url: "sqlite+aiosqlite:///local.sqlite3"
""".strip(),
        )

        config = Config.get(str(config_path))

        assert config.app.host == "127.0.0.1"
        assert config.app.port == 9000
        assert config.alchemy.url == "sqlite+aiosqlite:///local.sqlite3"

    def test_applies_environment_overrides(self, tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
app:
  host: "127.0.0.1"
  port: 9000
logging:
  file:
    enabled: false
auth:
  grpc_enabled: false
  grpc_target: "127.0.0.1:50052"
  grpc_timeout: 1.0
  grpc_host: "127.0.0.1"
  grpc_port: 50052
alchemy:
  url: "sqlite+aiosqlite:///local.sqlite3"
""".strip(),
        )
        monkeypatch.setenv("ECHOCUE_APP_PORT", "8001")
        monkeypatch.setenv("ECHOCUE_ALCHEMY_URL", "postgresql+asyncpg://user:pass@localhost:5432/echocue")
        monkeypatch.setenv("ECHOCUE_LOGGING_FILE_ENABLED", "true")
        monkeypatch.setenv("ECHOCUE_AUTH_GRPC_ENABLED", "true")
        monkeypatch.setenv("ECHOCUE_AUTH_GRPC_TARGET", "auth:50052")
        monkeypatch.setenv("ECHOCUE_AUTH_GRPC_TIMEOUT", "2.5")
        monkeypatch.setenv("ECHOCUE_AUTH_GRPC_HOST", "0.0.0.0")
        monkeypatch.setenv("ECHOCUE_AUTH_GRPC_PORT", "50053")
        monkeypatch.setenv("ECHOCUE_AUTH_SESSION_MAX_AGE_SECONDS", "14400")
        monkeypatch.setenv("ECHOCUE_AUTH_SESSION_RENEW_ON_ACCESS", "false")
        monkeypatch.setenv("ECHOCUE_LEXICON_GRPC_ENABLED", "true")
        monkeypatch.setenv("ECHOCUE_LEXICON_GRPC_TARGET", "lexicon:50051")
        monkeypatch.setenv("ECHOCUE_LEXICON_GRPC_TIMEOUT", "2.5")
        monkeypatch.setenv("ECHOCUE_LIVE_ROOM_STATUS_CACHE_TTL_SECONDS", "3600")
        monkeypatch.setenv("ECHOCUE_CLIENT_REMEDIATION_URL", "https://webui.example.test/remediation")
        monkeypatch.setenv("ECHOCUE_CLIENT_REMEDIATION_TOKEN_TTL_SECONDS", "600")

        config = Config.get(str(config_path))

        assert config.app.host == "127.0.0.1"
        assert config.app.port == 8001
        assert config.alchemy.url == "postgresql+asyncpg://user:pass@localhost:5432/echocue"
        assert config.logging.file.enabled is True
        assert config.auth.grpc_enabled is True
        assert config.auth.grpc_target == "auth:50052"
        assert config.auth.grpc_timeout == 2.5
        assert config.auth.grpc_host == "0.0.0.0"
        assert config.auth.grpc_port == 50053
        assert config.auth.session_max_age_seconds == 14_400
        assert config.auth.session_renew_on_access is False
        assert config.lexicon.grpc_enabled is True
        assert config.lexicon.grpc_target == "lexicon:50051"
        assert config.lexicon.grpc_timeout == 2.5
        assert config.live.room_status_cache_ttl_seconds == 3_600
        assert config.client.remediation_url == "https://webui.example.test/remediation"
        assert config.client.remediation_token_ttl_seconds == 600

    def test_rejects_invalid_boolean_environment_override(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setenv("ECHOCUE_LOGGING_FILE_ENABLED", "maybe")

        with pytest.raises(ValueError, match="Invalid boolean value"):
            Config().with_env_overrides()
