import os
import re
import unicodedata
from collections.abc import Iterable
from multiprocessing import get_all_start_methods
from pathlib import Path
from typing import Any, ClassVar, Self

import jieba  # type: ignore
import numpy as np
from fastembed import SparseEmbedding
from fastembed.common.utils import iter_batch
from fastembed.parallel_processor import ParallelWorkerPool
from fastembed.sparse.bm25 import Bm25, Bm25Worker

__all__ = (
    "Bm25CHWorker",
    "Bm25Chinese",
    "Bm25ChineseFactory",
)

_PUNCTUATION_REGEX: re.Pattern[str] = re.compile(r"[^\u4e00-\u9fffa-zA-Z0-9\-#]|\s+")


class Bm25Chinese(Bm25):
    """BM25 sparse embedder for Chinese text using jieba tokenization."""

    _stopwords_file: ClassVar[list["Path"]] = [Path("zh_stopwords.txt")]

    def __init__(
        self,
        model_name: str,
        cache_dir: str | None = None,
        *,
        k: float = 1.2,
        b: float = 0.75,
        avg_len: float = 256.0,
        language: str = "chinese",
        token_max_length: int = 40,
        disable_stemmer: bool = False,
        specific_model_path: str | None = None,
        **kwargs: Any,
    ) -> None:

        self.model_name = model_name
        self.cache_dir = cache_dir
        self.k = k
        self.b = b
        self.avg_len = avg_len
        self.language = language
        self.token_max_length = token_max_length
        self._specific_model_path = specific_model_path
        self._local_files_only = kwargs.get("local_files_only", False)

        self._model_dir = Path()

        if disable_stemmer:
            self.stopwords: set[str] = set()
            self.stemmer = None
        else:
            self.stopwords = set(self._load_stopwords(self._model_dir, self.language))
            self.stemmer = None

        self.tokenizer = self._tokenizer  # type: ignore

    @classmethod
    def _tokenizer(cls, document: str) -> list[str]:
        """Tokenize text using jieba search mode with Unicode normalization."""

        if not document.strip():
            return []

        # normalized = "".join(  # noqa: ERA001
        #     unicodedata.normalize("NFD", char) if unicodedata.category(char) != "Mn" else char for char in document
        # ).strip()

        normalized = unicodedata.normalize("NFKC", document.strip())

        return list(jieba.cut_for_search(normalized))

    @classmethod
    def _load_stopwords(cls, model_dir: Path, language: str) -> list[str]:
        """Load stopwords from configured files."""

        stopwords: list[str] = []

        for file in cls._stopwords_file:
            if not file.exists():
                continue

            with file.open() as f:
                stopwords.extend(line.strip() for line in f.read().splitlines() if line.strip())

        return stopwords

    def _stem(self, tokens: list[str]) -> list[str]:
        """Filter tokens by removing punctuation, stopwords, and overlength tokens."""

        stemmed: list[str] = []

        for token in tokens:
            if not _PUNCTUATION_REGEX.sub(" ", token).strip():
                continue

            if token.lower() in self.stopwords:
                continue

            if len(token) > self.token_max_length:
                continue

            stemmed.append(token)

        return stemmed

    def raw_embed(self, documents: list[str]) -> list[SparseEmbedding]:
        """Embed documents without batching or parallelism."""

        embeddings: list[SparseEmbedding] = []

        for document in documents:
            tokens = self._tokenizer(document)
            stemmed = self._stem(tokens)
            freq = self._term_frequency(stemmed)
            embeddings.append(SparseEmbedding.from_dict(freq))

        return embeddings

    def _embed_documents(
        self,
        model_name: str,
        cache_dir: str,
        documents: str | Iterable[str],
        batch_size: int = 256,
        parallel: int | None = None,
        local_files_only: bool = False,
        specific_model_path: str | None = None,
    ) -> Iterable[SparseEmbedding]:
        if isinstance(documents, str):
            documents = [documents]

        is_small = isinstance(documents, list) and len(documents) < batch_size

        if parallel is None or is_small:
            for batch in iter_batch(documents, batch_size):
                yield from self.raw_embed(batch)
            return

        if parallel == 0:
            parallel = os.cpu_count()

        start_method = "forkserver" if "forkserver" in get_all_start_methods() else "spawn"

        params = {
            "model_name": model_name,
            "cache_dir": cache_dir,
            "k": self.k,
            "b": self.b,
            "avg_len": self.avg_len,
            "language": self.language,
            "token_max_length": self.token_max_length,
            "disable_stemmer": self.disable_stemmer,
            "local_files_only": local_files_only,
            "specific_model_path": specific_model_path,
        }

        pool = ParallelWorkerPool(
            num_workers=parallel or 1,
            worker=self._get_worker_class(),
            start_method=start_method,
        )

        for batch in pool.ordered_map(iter_batch(documents, batch_size), **params):
            yield from batch

    def embed(
        self,
        documents: str | Iterable[str],
        batch_size: int = 256,
        parallel: int | None = None,
        **kwargs: Any,
    ) -> Iterable[SparseEmbedding]:
        """Embed documents into sparse vectors."""

        yield from self._embed_documents(
            model_name="",
            cache_dir=str(self.cache_dir),
            documents=documents,
            batch_size=batch_size,
            parallel=parallel,
            local_files_only=self._local_files_only,
            specific_model_path=self._specific_model_path,
        )

    def query_embed(self, query: str | Iterable[str], **kwargs: Any) -> Iterable[SparseEmbedding]:
        """Embed queries into sparse vectors with binary weighting."""

        if isinstance(query, str):
            query = [query]

        for text in query:
            tokens = self._tokenizer(text)
            stemmed = self._stem(tokens)
            indices = np.array(
                list({self.compute_token_id(token) for token in stemmed}),
                dtype=np.int32,
            )
            values = np.ones_like(indices)

            yield SparseEmbedding(indices=indices, values=values)

    @classmethod
    def _get_worker_class(cls) -> type["Bm25CHWorker"]:
        return Bm25CHWorker


class Bm25CHWorker(Bm25Worker):
    """Worker for parallel BM25 Chinese embedding."""

    def __init__(self, model_name: str, cache_dir: str, **kwargs: Any) -> None:
        self.model = Bm25Chinese(model_name, cache_dir, **kwargs)

    @classmethod
    def start(cls, model_name: str, cache_dir: str, **kwargs: Any) -> Self:
        return cls(model_name, cache_dir, **kwargs)

    def process(self, items: Iterable[tuple[int, Any]]) -> Iterable[tuple[int, list[SparseEmbedding]]]:
        for idx, batch in items:
            yield idx, self.model.raw_embed(batch)


class Bm25ChineseFactory:
    """Factory for creating and reusing Bm25Chinese instances."""

    def __init__(
        self,
        *,
        k: float = 1.2,
        b: float = 0.75,
        avg_len: float = 256.0,
        language: str = "chinese",
        token_max_length: int = 40,
        disable_stemmer: bool = False,
    ) -> None:
        self._k = k
        self._b = b
        self._avg_len = avg_len
        self._language = language
        self._token_max_length = token_max_length
        self._disable_stemmer = disable_stemmer
        self._instance: Bm25Chinese | None = None

    def new(self, model_name: str = "bm25-chinese", cache_dir: str | None = None) -> Bm25Chinese:
        """Create or return cached Bm25Chinese instance."""

        if self._instance is None:
            self._instance = Bm25Chinese(
                model_name=model_name,
                cache_dir=cache_dir,
                k=self._k,
                b=self._b,
                avg_len=self._avg_len,
                language=self._language,
                token_max_length=self._token_max_length,
                disable_stemmer=self._disable_stemmer,
            )

        return self._instance
