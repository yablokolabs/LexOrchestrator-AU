from lexorchestrator_au.rag.embeddings import EmbeddingProvider
from lexorchestrator_au.rag.repository import DocumentRepository
from lexorchestrator_au.rag.reranker import SimpleLegalReranker
from lexorchestrator_au.rag.types import RetrievalFilters, RetrievalResult


class RetrievalService:
    def __init__(
        self,
        repository: DocumentRepository,
        embeddings: EmbeddingProvider,
        reranker: SimpleLegalReranker | None = None,
    ) -> None:
        self.repository = repository
        self.embeddings = embeddings
        self.reranker = reranker or SimpleLegalReranker()

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilters,
        limit: int,
    ) -> list[RetrievalResult]:
        query_embedding = await self.embeddings.embed_query(query)
        # Over-fetch 3x for reranking headroom
        over_fetch = limit * 3
        results = await self.repository.hybrid_search(
            query, query_embedding, filters, limit=over_fetch
        )
        return self.reranker.rerank(query, results, filters, limit=limit)
