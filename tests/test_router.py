from lexorchestrator_au.orchestration.router import ModelRouter


def test_router_sends_case_law_to_managed_chain_first() -> None:
    plan = ModelRouter().route("What did the High Court hold in this authority?")

    assert plan.query_type == "case_law"
    assert plan.providers[:2] == ["anthropic", "openai"]
    assert plan.providers[-1] == "llama"


def test_router_prefers_openai_for_drafting() -> None:
    plan = ModelRouter().route("Draft a concise settlement clause")

    assert plan.query_type == "drafting"
    assert plan.providers[0] == "openai"


def test_routine_research_keeps_extract_fallback_last() -> None:
    plan = ModelRouter().route("What are the key legal principles?")

    assert plan.query_type == "legal_research"
    assert plan.providers[:2] == ["openai", "anthropic"]
    assert plan.providers[-1] == "llama"
