from pathlib import Path

import pytest

from fake_embedder import FakeEmbedder

from omnemo.config import Config
from omnemo.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "store.db", FakeEmbedder(), Config())
    yield s
    s.close()
