from echocue.base.schema import BaseStruct

__all__ = ("ClientConfig",)


class ClientConfig(BaseStruct):
    """Desktop client interaction configuration."""

    remediation_url: str = "http://localhost:3000/remediation"
    remediation_token_ttl_seconds: int = 15 * 60
