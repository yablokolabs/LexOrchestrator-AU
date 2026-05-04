from prometheus_client import Counter, Histogram, generate_latest

QUERY_LATENCY = Histogram(
    "lex_query_latency_seconds",
    "End-to-end query latency",
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
LLM_FAILURES = Counter("lex_llm_failures_total", "LLM provider failures", ["provider"])
LLM_REQUESTS = Counter("lex_llm_requests_total", "LLM provider requests", ["provider", "status"])
RETRIEVAL_EMPTY = Counter("lex_retrieval_empty_total", "Queries with no retrieved sources")
FEEDBACK_EVENTS = Counter("lex_feedback_events_total", "Feedback events", ["rating"])


def metrics_bytes() -> bytes:
    return generate_latest()
