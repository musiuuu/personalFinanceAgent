import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import Document
from app.retrieval.vector import chunk_text, embed, index_document, search


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_embeddings_are_normalized_and_deterministic():
    a = embed("invoice payment terms net 30")
    b = embed("invoice payment terms net 30")
    assert (a == b).all()
    assert abs(float((a * a).sum()) - 1.0) < 1e-5


def test_chunking_covers_text():
    text = ("Payment is due within 30 days. " * 80).strip()
    chunks = chunk_text(text, max_chars=200)
    assert all(len(c) <= 200 for c in chunks)
    assert "".join(chunks).count("Payment") >= text.count("Payment") * 0.9


def test_index_and_search_returns_relevant_chunk(session):
    doc = Document(filename="invoice.pdf", file_type="invoice")
    session.add(doc)
    session.flush()
    index_document(
        session,
        doc.id,
        "Invoice 4411 from TechVendor. Payment terms: net 30 days. "
        "Warranty: 12 months on laptop hardware. Delivery to Karachi office.",
    )
    other = Document(filename="other.pdf", file_type="invoice")
    session.add(other)
    session.flush()
    index_document(
        session, other.id, "Electricity tariff schedule for residential consumers."
    )
    session.commit()

    results = search(session, "what were the warranty terms on the laptop invoice?")
    assert results
    top_score, top_chunk = results[0]
    assert top_chunk.source_doc_id == doc.id
    assert "Warranty" in top_chunk.text or "net 30" in top_chunk.text
