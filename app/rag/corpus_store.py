"""
Mirror of every chunk upserted into Pinecone, used for BM25 lexical search.

Pinecone is great for dense/vector search but doesn't give a cheap way to
pull "every raw chunk for topic X" back out for lexical scoring. This lives
in Postgres (not a local file) specifically because most PaaS free tiers
(Render included) don't provide a persistent disk -- a local JSON file
would silently get wiped on every restart or redeploy.

These functions open their own short-lived DB session rather than taking
one as a parameter, since they're called from app/rag/retriever.py, which
isn't itself a FastAPI request handler with a request-scoped session
available.
"""

from app.db.database import SessionLocal
from app.db.models import CorpusChunk


def load_corpus() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(CorpusChunk).all()
        return [{"id": r.id, "text": r.text, "topic": r.topic} for r in rows]
    finally:
        db.close()


def add_to_corpus(chunks: list[dict]) -> None:
    """Upsert semantics keyed by id -- re-adding a chunk with the same id
    overwrites it, matching Pinecone's own upsert behavior."""
    db = SessionLocal()
    try:
        for chunk in chunks:
            existing = db.query(CorpusChunk).filter(CorpusChunk.id == chunk["id"]).first()
            if existing:
                existing.text = chunk["text"]
                existing.topic = chunk["topic"]
            else:
                db.add(CorpusChunk(id=chunk["id"], text=chunk["text"], topic=chunk["topic"]))
        db.commit()
    finally:
        db.close()


def corpus_for_topic(topic: str) -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(CorpusChunk).filter(CorpusChunk.topic == topic).all()
        return [{"id": r.id, "text": r.text, "topic": r.topic} for r in rows]
    finally:
        db.close()
