"""list_all returns every memory in a namespace, not just the first page.

Uses a fake embedding model, so no OPENAI_API_KEY is needed.
"""

import pytest
from langchain_core.embeddings import Embeddings

from memable import Memory, build_duckdb_store, build_sqlite_store

DIMS = 8


class _FlatEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text):
        return [float(len(text) % 7 + 1)] + [1.0] * (DIMS - 1)


def _fill(store, namespace, count):
    """Write memories straight to the backend: no embedding call per item."""
    for i in range(count):
        memory = Memory(text=f"memory {i}")
        store.raw_store.put(namespace, str(memory.id), memory.to_store_value())


@pytest.fixture(params=["sqlite", "duckdb"])
def store(request, tmp_path):
    embeddings = _FlatEmbeddings()
    if request.param == "sqlite":
        cm = build_sqlite_store(":memory:", embeddings=embeddings, dims=DIMS)
    else:
        cm = build_duckdb_store(str(tmp_path / "m.duckdb"), embeddings=embeddings, dims=DIMS)
    with cm as s:
        s.setup()
        yield s


def test_list_all_returns_more_than_one_page(store):
    namespace = ("paging", "test")
    _fill(store, namespace, 1205)

    memories = store.list_all(namespace)

    assert len(memories) == 1205
    assert len({m.id for m in memories}) == 1205


def test_backend_search_offset_pages_without_overlap(store):
    namespace = ("paging", "offset")
    _fill(store, namespace, 7)

    first = store.raw_store.search(namespace, query=None, limit=4, offset=0)
    second = store.raw_store.search(namespace, query=None, limit=4, offset=4)

    assert len(first) == 4
    assert len(second) == 3
    assert not {i.key for i in first} & {i.key for i in second}
