from qdrant_client.models import SparseVector

from echocue.base import BaseStruct

__all__ = (
    "DenseVector",
    "HybridVector",
    "MultiVector",
    "SparseVector",
)


class DenseVector(BaseStruct):
    """Simplified dense vector representation."""

    index: int
    values: list[float]


class HybridVector(BaseStruct):
    """Hybrid vector representation."""

    dense: DenseVector
    sparse: SparseVector


class MultiVector(BaseStruct):
    """Multi-vector representation."""

    dense_full: DenseVector
    dense_mrl: DenseVector | None = None
    sparse: SparseVector | None = None
