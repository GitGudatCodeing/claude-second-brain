"""Shared fixtures. Tests never load the real embedding model or touch the real index."""
from __future__ import annotations

import math
import re
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for sub in ("mcp", "scripts", "eval"):
    sys.path.insert(0, str(ROOT / sub))

import server  # noqa: E402


def fake_embed(texts: list[str]) -> list[bytes]:
    """Deterministic bag-of-words vectors: texts sharing words end up close."""
    import sqlite_vec

    out = []
    for t in texts:
        v = [0.0] * server.DIM
        for tok in re.findall(r"\w+", t.lower()):
            v[zlib.crc32(tok.encode()) % server.DIM] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append(sqlite_vec.serialize_float32([x / n for x in v]))
    return out


@pytest.fixture
def index(tmp_path, monkeypatch):
    """A fresh index in a temp file, with the fake embedder."""
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "index.db")
    monkeypatch.setattr(server, "_db", None)
    monkeypatch.setattr(server, "embed", fake_embed)
    yield server
    if server._db is not None:
        server._db.close()
        server._db = None


@pytest.fixture
def vault(tmp_path):
    """A small folder of notes to index."""
    root = tmp_path / "vault"
    files = {
        "notes/garden.md": "# Garden\n\n## Watering\nThe tomatoes need water every morning in July.\n",
        "notes/bikes.md": "# Bikes\n\n## Tyres\nPump the road bike tyres to six bar before a ride.\n",
        "notes/private/diary.md": "# Diary\n\nSecret plans for the tomatoes.\n",
        "code/app.py": "def water_tomatoes():\n    return 'done'\n",
        "node_modules/pkg/readme.md": "# Should never be indexed\n",
        "image.png": "not text",
        ".indexignore": "notes/private  # personal\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root
