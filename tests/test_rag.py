"""
RAG tests: citation present, unanswerable refused, correct KB file cited.
"""
import pytest


def post_ask(client, property_id: str, question: str):
    return client.post("/ask", json={"property_id": property_id, "question": question})


def test_rag_rates_citation(client):
    """'how do I change my room rate' → answer from kb/rates.md with citation."""
    r = post_ask(client, "hotel_a", "how do I change my room rate for a date?")
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] is not None, "RAG answer must not be None"
    assert data["source"] is not None, "RAG must cite a source"
    assert "rates" in (data["source"] or "").lower(), (
        f"Expected rates.md citation, got source={data['source']!r}"
    )


def test_rag_reviews_citation(client):
    """'how do I respond to an OTA review' → answer from kb/reviews.md."""
    r = post_ask(client, "hotel_a", "how do I respond to an OTA review?")
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] is not None
    assert data["source"] is not None
    assert "review" in (data["source"] or "").lower(), (
        f"Expected reviews.md citation, got source={data['source']!r}"
    )


def test_rag_unanswerable_refused(client):
    """A question outside the KB must be refused (not fabricated)."""
    r = post_ask(client, "hotel_a", "what is the capital of Mars?")
    assert r.status_code == 200
    data = r.json()
    assert data.get("refused") is True or data.get("answer") is None, (
        f"Out-of-KB question should be refused. Got answer={data.get('answer')!r}"
    )


def test_rag_answer_grounded(client):
    """Answer must not hallucinate — it should relate to the KB content."""
    r = post_ask(client, "hotel_a", "how do I onboard a new property?")
    assert r.status_code == 200
    data = r.json()
    if not data.get("refused"):
        assert data["answer"] is not None
        assert data["source"] is not None
        assert "onboard" in (data["source"] or "").lower() or "onboard" in (data["answer"] or "").lower()
