from pathlib import Path

import pytest
from pytest import MonkeyPatch

from echocue.base import Config


class TestConfig:
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
alchemy:
  url: "sqlite+aiosqlite:///local.sqlite3"
""".strip(),
        )
        monkeypatch.setenv("ECHOCUE_APP_PORT", "8001")
        monkeypatch.setenv("ECHOCUE_ALCHEMY_URL", "postgresql+asyncpg://user:pass@localhost:5432/echocue")
        monkeypatch.setenv("ECHOCUE_LOGGING_FILE_ENABLED", "true")
        monkeypatch.setenv("ECHOCUE_LEXICON_GRPC_ENABLED", "true")
        monkeypatch.setenv("ECHOCUE_LEXICON_GRPC_TARGET", "lexicon:50051")
        monkeypatch.setenv("ECHOCUE_LEXICON_GRPC_TIMEOUT", "2.5")

        config = Config.get(str(config_path))

        assert config.app.host == "127.0.0.1"
        assert config.app.port == 8001
        assert config.alchemy.url == "postgresql+asyncpg://user:pass@localhost:5432/echocue"
        assert config.logging.file.enabled is True
        assert config.lexicon.grpc_enabled is True
        assert config.lexicon.grpc_target == "lexicon:50051"
        assert config.lexicon.grpc_timeout == 2.5

    def test_rejects_invalid_boolean_environment_override(self, monkeypatch: MonkeyPatch) -> None:
        monkeypatch.setenv("ECHOCUE_LOGGING_FILE_ENABLED", "maybe")

        with pytest.raises(ValueError, match="Invalid boolean value"):
            Config().with_env_overrides()
