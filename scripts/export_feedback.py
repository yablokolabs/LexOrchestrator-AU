#!/usr/bin/env python3
"""Export corrected feedback examples to JSONL."""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lexorchestrator_au.core.config import get_settings  # noqa: E402
from lexorchestrator_au.db.session import create_engine, create_session_factory  # noqa: E402
from lexorchestrator_au.feedback.export import FineTuningDatasetExporter  # noqa: E402


async def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "exports" / "feedback_dataset.jsonl"
    settings = get_settings()
    engine = create_engine(settings)
    try:
        exporter = FineTuningDatasetExporter(create_session_factory(engine))
        print(await exporter.export_jsonl(output))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
