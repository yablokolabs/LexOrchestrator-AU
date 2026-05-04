import asyncio
from pathlib import Path

from lexorchestrator_au.core.config import get_settings
from lexorchestrator_au.db.session import create_engine, create_session_factory
from lexorchestrator_au.feedback.export import FineTuningDatasetExporter

PROJECT_ROOT = Path(__file__).resolve().parents[3]


async def run(output_path: Path | None = None) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        exporter = FineTuningDatasetExporter(create_session_factory(engine))
        await exporter.export_jsonl(
            output_path or PROJECT_ROOT / "exports" / "feedback_dataset.jsonl"
        )
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
