import asyncio
import json
from pathlib import Path
from typing import Any

from lexorchestrator_au.rag.chunker import LegalChunker
from lexorchestrator_au.rag.embeddings import EmbeddingProvider
from lexorchestrator_au.rag.repository import DocumentRepository
from lexorchestrator_au.rag.types import SourceDocument


class IngestionPipeline:
    def __init__(
        self,
        repository: DocumentRepository,
        embeddings: EmbeddingProvider,
        chunker: LegalChunker | None = None,
        batch_size: int = 64,
    ) -> None:
        self.repository = repository
        self.embeddings = embeddings
        self.chunker = chunker or LegalChunker()
        self.batch_size = batch_size

    async def ingest_document(self, document: SourceDocument) -> dict[str, Any]:
        chunks = self.chunker.chunk(document)
        embeddings: list[list[float]] = []
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start : start + self.batch_size]
            embeddings.extend(await self.embeddings.embed_texts([chunk.text for chunk in batch]))
        document_id = await self.repository.replace_document(document, chunks, embeddings)
        return {"document_id": str(document_id), "source_uri": document.source_uri, "chunks": len(chunks)}

    async def ingest_json_dir(self, path: Path) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        files = await asyncio.to_thread(lambda: sorted(path.glob("*.json")))
        for file_path in files:
            raw = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
            payload = json.loads(raw)
            document = SourceDocument(
                source_uri=payload["source_uri"],
                title=payload["title"],
                jurisdiction=payload.get("jurisdiction", "AU"),
                court=payload.get("court"),
                case_type=payload.get("case_type"),
                doc_type=payload.get("doc_type"),
                citation=payload.get("citation"),
                effective_date=payload.get("effective_date"),
                text=payload["text"],
                metadata=payload.get("metadata", {}),
            )
            results.append(await self.ingest_document(document))
        return results
