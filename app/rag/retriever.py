"""
Hybrid retriever for NEXUS, same pattern used in RAG-Forge:

  1. Dense retrieval from Pinecone (semantic similarity)
  2. Sparse retrieval via local BM25 (lexical/keyword match)
  3. Reciprocal Rank Fusion (RRF) to combine both ranked lists
  4. Cross-encoder reranking of the fused candidates for the final order

Why bother with sparse + fusion + reranking here specifically: interview
prep chunks lean on exact terminology ("CAP theorem", "cross-encoder",
"window function") that dense embeddings can under-weight in favor of
looser semantic similarity. BM25 catches the exact-term matches, RRF
combines both rankings without hand-tuned weights, and the cross-encoder
does a more expensive but more accurate final pass over just the fused
candidate pool (cheap because it only scores ~10 pairs, not the whole
corpus).
"""

from rank_bm25 import BM25Okapi
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.config import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_ENVIRONMENT,
    EMBEDDING_MODEL,
    RERANKER_MODEL,
)
from app.rag.corpus_store import add_to_corpus, corpus_for_topic

_pc = Pinecone(api_key=PINECONE_API_KEY)

_embedder = None
_reranker = None
_index = None


def get_embedder():
    """Lazy-loaded so importing this module never requires network access."""
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANKER_MODEL)
    return _reranker


def ensure_index_exists():
    embed_dim = get_embedder().get_sentence_embedding_dimension()
    existing = [idx["name"] for idx in _pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing:
        _pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=embed_dim,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=PINECONE_ENVIRONMENT),
        )
    return _pc.Index(PINECONE_INDEX_NAME)


def get_index():
    global _index
    if _index is None:
        _index = ensure_index_exists()
    return _index


def upsert_material(chunks: list[dict]):
    """
    chunks: list of {"id": str, "text": str, "topic": str}
    Embeds and upserts into Pinecone (dense) and mirrors into the local
    corpus store (for BM25 sparse search).
    """
    index = get_index()
    embedder = get_embedder()
    vectors = []
    for chunk in chunks:
        embedding = embedder.encode(chunk["text"]).tolist()
        vectors.append(
            {
                "id": chunk["id"],
                "values": embedding,
                "metadata": {"text": chunk["text"], "topic": chunk["topic"]},
            }
        )
    index.upsert(vectors=vectors)
    add_to_corpus(chunks)


def _dense_search(topic: str, query: str, top_k: int) -> list[tuple[str, str]]:
    """Returns ranked [(id, text), ...] from Pinecone dense search."""
    index = get_index()
    query_embedding = get_embedder().encode(query).tolist()

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        filter={"topic": {"$eq": topic}},
        include_metadata=True,
    )
    return [(m["id"], m["metadata"]["text"]) for m in results.get("matches", [])]


def _sparse_search(topic: str, query: str, top_k: int) -> list[tuple[str, str]]:
    """Returns ranked [(id, text), ...] from local BM25 over this topic's chunks."""
    corpus = corpus_for_topic(topic)
    if not corpus:
        return []

    tokenized_corpus = [c["text"].lower().split() for c in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query.lower().split())

    ranked = sorted(zip(corpus, scores), key=lambda pair: pair[1], reverse=True)
    return [(c["id"], c["text"]) for c, score in ranked[:top_k] if score > 0]


def _reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, str]]], k: int = 60
) -> list[tuple[str, str]]:
    """
    Combines multiple ranked (id, text) lists into one fused ranking using
    RRF: score(doc) = sum(1 / (k + rank)) across all lists it appears in.
    A doc that ranks well in *either* list (or both) rises to the top,
    without needing to hand-tune how much to trust dense vs. sparse.
    """
    scores: dict[str, float] = {}
    texts: dict[str, str] = {}

    for ranked in ranked_lists:
        for rank, (doc_id, text) in enumerate(ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            texts[doc_id] = text

    fused = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return [(doc_id, texts[doc_id]) for doc_id, _ in fused]


def retrieve_context(
    topic: str, query: str, top_k: int = 3, fusion_pool: int = 10
) -> str:
    """
    Full hybrid pipeline: dense + sparse -> RRF fusion -> cross-encoder
    rerank -> top_k. Retrieves top_k relevant chunks for the given topic +
    query, concatenated into a single context string.
    """
    dense = _dense_search(topic, query, top_k=fusion_pool)
    sparse = _sparse_search(topic, query, top_k=fusion_pool)

    if not dense and not sparse:
        return ""

    fused = _reciprocal_rank_fusion([dense, sparse])[:fusion_pool]
    if not fused:
        return ""

    reranker = get_reranker()
    pairs = [[query, text] for _, text in fused]
    rerank_scores = reranker.predict(pairs)

    reranked = sorted(zip(fused, rerank_scores), key=lambda pair: pair[1], reverse=True)
    top_chunks = [text for (_id, text), _score in reranked[:top_k]]

    return "\n---\n".join(top_chunks)
