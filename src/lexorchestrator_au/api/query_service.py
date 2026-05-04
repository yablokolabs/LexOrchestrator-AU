import time
import uuid

from lexorchestrator_au.api.schemas import QueryRequest, QueryResponse
from lexorchestrator_au.attribution.service import AttributionService, ConfidenceScorer
from lexorchestrator_au.core.config import Settings
from lexorchestrator_au.core.metrics import QUERY_LATENCY, RETRIEVAL_EMPTY
from lexorchestrator_au.feedback.service import FeedbackService
from lexorchestrator_au.orchestration.orchestrator import LLMOrchestrator
from lexorchestrator_au.rag.retrieval import RetrievalService
from lexorchestrator_au.rag.types import RetrievalFilters


class QueryService:
    def __init__(
        self,
        retrieval: RetrievalService,
        orchestrator: LLMOrchestrator,
        attribution: AttributionService,
        confidence: ConfidenceScorer,
        feedback: FeedbackService,
        settings: Settings,
    ) -> None:
        self.retrieval = retrieval
        self.orchestrator = orchestrator
        self.attribution = attribution
        self.confidence = confidence
        self.feedback = feedback
        self.settings = settings

    async def query(self, request: QueryRequest, trace_id: str | None = None) -> QueryResponse:
        start = time.perf_counter()
        trace_id = trace_id or str(uuid.uuid4())
        filters = RetrievalFilters(
            jurisdiction=request.jurisdiction,
            court=request.court,
            case_type=request.case_type,
            doc_type=request.doc_type,
        )

        limit = max(request.max_citations, self.settings.retrieval_limit)
        results = await self.retrieval.retrieve(request.query, filters, limit=limit)
        if not results:
            RETRIEVAL_EMPTY.inc()

        context_blocks = self.attribution.context_blocks(results, max_blocks=self.settings.retrieval_limit)
        llm_response, metadata = await self.orchestrator.generate(
            query=request.query,
            context_blocks=context_blocks,
            jurisdiction=request.jurisdiction,
            trace_id=trace_id,
            explicit_query_type=request.query_type,
        )
        citations = self.attribution.build_citations(results, max_citations=request.max_citations)
        confidence = self.confidence.score(results, citations, llm_response.degraded)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        QUERY_LATENCY.observe(latency_ms / 1000)

        payload = QueryResponse(
            trace_id=trace_id,
            answer=llm_response.answer,
            citations=citations,
            confidence_score=confidence,
            model_used=llm_response.model,
            provider=llm_response.provider,
            degraded=llm_response.degraded,
            latency_ms=latency_ms,
            metadata={
                **metadata,
                "client_matter_id": request.client_matter_id,
                "retrieved_chunks": len(results),
                "token_usage": llm_response.token_usage,
                "finish_reason": llm_response.finish_reason,
            },
        )

        await self._record_query_run(request, filters, payload)
        return payload

    async def _record_query_run(
        self,
        request: QueryRequest,
        filters: RetrievalFilters,
        response: QueryResponse,
    ) -> None:
        try:
            await self.feedback.record_query_run(
                trace_id=response.trace_id,
                user_query=request.query,
                jurisdiction=request.jurisdiction,
                filters={
                    "court": filters.court,
                    "case_type": filters.case_type,
                    "doc_type": filters.doc_type,
                    "client_matter_id": request.client_matter_id,
                },
                response=response.model_dump(mode="json"),
                model_used=response.model_used,
                confidence=response.confidence_score,
                latency_ms=response.latency_ms,
                degraded=response.degraded,
            )
        except Exception:
            # Feedback flywheel should not break live research responses.
            return None
