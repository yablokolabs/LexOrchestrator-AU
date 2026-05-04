import uuid


def test_invalid_trace_id_is_replaced() -> None:
    incoming = "not-a-uuid"
    try:
        trace_id = str(uuid.UUID(incoming)) if incoming else str(uuid.uuid4())
    except (TypeError, ValueError):
        trace_id = str(uuid.uuid4())

    assert uuid.UUID(trace_id)
    assert trace_id != incoming
