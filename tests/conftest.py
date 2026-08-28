from pathlib import Path

import pytest

from omnemo.config import Config
from omnemo.embedder import FakeEmbedder
from omnemo.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "store.db", FakeEmbedder(), Config(embedder="fake"))
    yield s
    s.close()
