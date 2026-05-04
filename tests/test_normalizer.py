from lexorchestrator_au.orchestration.normalizer import normalize_answer


class TestNormalizeAnswer:
    def test_plain_text_passthrough(self) -> None:
        answer, meta = normalize_answer("This is a plain text answer.")
        assert answer == "This is a plain text answer."
        assert meta == {"limitations": []}

    def test_json_answer_extraction(self) -> None:
        answer, meta = normalize_answer('{"answer": "The law says X.", "limitations": []}')
        assert answer == "The law says X."
        assert meta == {"limitations": []}

    def test_json_response_key_fallback(self) -> None:
        answer, _meta = normalize_answer('{"response": "Alternative key."}')
        assert answer == "Alternative key."

    def test_empty_answer_string_preserved(self) -> None:
        """Empty string answer should NOT be replaced with raw JSON."""
        answer, meta = normalize_answer('{"answer": "", "limitations": ["insufficient"]}')
        assert answer == ""
        assert "limitations" in meta

    def test_empty_input(self) -> None:
        answer, meta = normalize_answer("")
        assert answer == ""
        assert meta == {"limitations": ["empty_model_response"]}

    def test_whitespace_only(self) -> None:
        answer, meta = normalize_answer("   \n  ")
        assert answer == ""
        assert meta == {"limitations": ["empty_model_response"]}

    def test_non_dict_json(self) -> None:
        answer, _meta = normalize_answer("[1, 2, 3]")
        assert answer == "[1, 2, 3]"
