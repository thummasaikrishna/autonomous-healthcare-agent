import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("PUBMED_EMAIL", "test@example.com")


@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_app.db")
