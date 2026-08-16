from aigc.base.schema import BaseStruct

__all__ = ("ClassifierConfig",)


class ClassifierConfig(BaseStruct):
    """Configuration for live semantic classification."""

    grpc_enabled: bool = False
    grpc_target: str = "127.0.0.1:50051"
    grpc_timeout: float = 1.0
    grpc_host: str = "127.0.0.1"
    grpc_port: int = 50051
    collection_name: str = "live_lexicon"
