"""
One-time (or repeatable) script to load prep material into Pinecone.

Usage (from the project root, with your venv active and .env configured):

    python -m scripts.seed_pinecone

Upserts are idempotent by `id` -- re-running this after editing
app/rag/seed_data.py will just overwrite the existing vectors, not
duplicate them. Add your own chunks to SEED_CHUNKS (or write a second
script pulling from your own notes/PDFs) as your material grows.
"""

from app.rag.retriever import upsert_material
from app.rag.seed_data import SEED_CHUNKS


def main():
    topics = sorted({chunk["topic"] for chunk in SEED_CHUNKS})
    print(f"Seeding {len(SEED_CHUNKS)} chunks across {len(topics)} topics:")
    for topic in topics:
        count = sum(1 for c in SEED_CHUNKS if c["topic"] == topic)
        print(f"  - {topic}: {count} chunks")

    upsert_material(SEED_CHUNKS)
    print("\nDone. Pinecone index is ready for retrieval.")


if __name__ == "__main__":
    main()
