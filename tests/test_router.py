from lexorchestrator_au.orchestration.router import ModelRouter


class TestModelRouter:
    def test_case_law_routes_anthropic_first(self) -> None:
        plan = ModelRouter().route("What did the High Court hold in this authority?")
        assert plan.query_type == "case_law"
        assert plan.providers[:2] == ("anthropic", "openai")
        assert plan.providers[-1] == "llama"

    def test_drafting_routes_openai_first(self) -> None:
        plan = ModelRouter().route("Draft a concise settlement clause")
        assert plan.query_type == "drafting"
        assert plan.providers[0] == "openai"

    def test_routine_research_keeps_extract_fallback_last(self) -> None:
        plan = ModelRouter().route("What are the key legal principles?")
        assert plan.query_type == "legal_research"
        assert plan.providers[:2] == ("openai", "anthropic")
        assert plan.providers[-1] == "llama"

    def test_statutory_interpretation(self) -> None:
        plan = ModelRouter().route("What does section 387 of the Fair Work Act require?")
        assert plan.query_type == "statutory_interpretation"
        assert plan.providers[0] == "anthropic"

    def test_explicit_type_overrides_classification(self) -> None:
        plan = ModelRouter().route("Hello world", explicit_type="drafting")
        assert plan.query_type == "drafting"

    def test_complex_analysis_for_long_queries(self) -> None:
        long_query = " ".join(["word"] * 81)
        plan = ModelRouter().route(long_query)
        assert plan.query_type == "complex_analysis"

    def test_word_boundary_matching(self) -> None:
        # "act" should NOT match inside "actually" or "practice"
        plan = ModelRouter().route("What is actually the best practice here?")
        assert plan.query_type == "legal_research"

    def test_providers_are_immutable_tuples(self) -> None:
        plan = ModelRouter().route("test query")
        assert isinstance(plan.providers, tuple)
