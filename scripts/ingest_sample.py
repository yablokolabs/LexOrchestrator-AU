#!/usr/bin/env python3
"""Ingest bundled mock Australian legal documents into PostgreSQL/pgvector."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lexorchestrator_au.scripts.ingest_sample import run  # noqa: E402

if __name__ == "__main__":
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "mock_legal_docs"
    asyncio.run(run(data_dir=data_dir))
