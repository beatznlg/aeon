"""
AEON OS Phase 7 — Vector Store & Hybrid Search
================================================
Pluggable vector persistence for RAG knowledge bases.

Backends:
- DiskVectorStore: JSONL on disk, in-memory search (fallback, zero extra deps)
- SupabaseVectorStore: persists embeddings to Supabase pgvector

Search modes:
- vector: cosine similarity over embeddings
- keyword: BM25-lite (disk) or Postgres full-text search (Supabase)
- hybrid: Reciprocal Rank Fusion of vector + keyword results
"""

import json
import math
import os
import re
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

# === helpers ==============================================================

def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def _normalize(vec: list[float]) -> np.ndarray:
    v = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def _pad_embedding(vec: list[float], dim: int = 1536) -> list[float]:
    """Pad or truncate a vector to a fixed dimension for pgvector storage."""
    if len(vec) >= dim:
        return vec[:dim]
    return vec + [0.0] * (dim - len(vec))


# === Keyword scoring (BM25-lite) ===========================================

class KeywordScorer:
    """Lightweight BM25/TF-IDF scorer with no external deps."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: list[tuple[str, str, list[str]]] = []  # (id, raw_text, tokens)
        self._avgdl = 0.0
        self._idf: dict[str, float] = {}

    def index(self, chunks: list[dict[str, Any]]):
        """Index chunk records."""
        self._docs = []
        total_len = 0
        for rec in chunks:
            text = rec.get("text", "")
            tokens = _tokenize(text)
            self._docs.append((rec.get("id"), text, tokens))
            total_len += len(tokens)
        self._avgdl = total_len / max(len(self._docs), 1)

        # Compute IDF for each term
        n = len(self._docs)
        df: dict[str, int] = Counter()
        for _, _, tokens in self._docs:
            seen = set(tokens)
            for t in seen:
                df[t] += 1
        self._idf = {t: math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1.0) for t in df}

    def score(self, query: str) -> list[tuple[str, float]]:
        """Return list of (chunk_id, bm25_score) for the query."""
        if not self._docs:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        results = []
        for chunk_id, _, tokens in self._docs:
            if not tokens:
                continue
            dl = len(tokens)
            tf = Counter(tokens)
            score = 0.0
            for t in q_tokens:
                idf = self._idf.get(t, 0.0)
                if idf == 0:
                    continue
                f = tf.get(t, 0)
                denom = f + self.k1 * (1 - self.b + self.b * (dl / self._avgdl))
                score += idf * (f * (self.k1 + 1)) / (denom + 1e-9)
            if score > 0:
                results.append((chunk_id, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return results


# === Vector Store ABC ======================================================

class VectorStore(ABC):
    @abstractmethod
    def add_chunks(self, kb_id: str, doc_id: str, chunks: list[dict[str, Any]]) -> None:
        """Persist chunk records for a document."""
        raise NotImplementedError

    @abstractmethod
    def search_vector(self, kb_id: str, query_vec: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """Return top_k chunks by vector similarity. Each result has id, doc_id, text, score."""
        raise NotImplementedError

    @abstractmethod
    def search_keyword(self, kb_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top_k chunks by keyword relevance."""
        raise NotImplementedError

    def search_hybrid(self, kb_id: str, query: str, query_vec: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        """RRF fusion of vector and keyword results."""
        vector_results = self.search_vector(kb_id, query_vec, top_k=max(top_k, 20))
        keyword_results = self.search_keyword(kb_id, query, top_k=max(top_k, 20))
        return reciprocal_rank_fusion(vector_results, keyword_results, top_k=top_k)

    @abstractmethod
    def delete_kb(self, kb_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def stats(self, kb_id: str) -> dict[str, Any]:
        raise NotImplementedError


def reciprocal_rank_fusion(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Combine ranked lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    details: dict[str, dict[str, Any]] = {}

    for rank, item in enumerate(vector_results, start=1):
        idx = item["id"]
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
        details[idx] = {**item, "vector_rank": rank, "keyword_rank": None}

    for rank, item in enumerate(keyword_results, start=1):
        idx = item["id"]
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
        if idx in details:
            details[idx]["keyword_rank"] = rank
        else:
            details[idx] = {**item, "vector_rank": None, "keyword_rank": rank}

    # Sort by score descending, then by id for determinism
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return [
        {
            **details[idx],
            "rrf_score": round(score, 6),
        }
        for idx, score in ranked[:top_k]
    ]


# === Disk Vector Store =====================================================

class DiskVectorStore(VectorStore):
    """JSONL-backed vector store with in-memory search."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.kb_dir = self.root / "knowledge_bases"
        self.kb_dir.mkdir(parents=True, exist_ok=True)

    def _chunks_file(self, kb_id: str) -> Path:
        kb_path = self.kb_dir / kb_id
        kb_path.mkdir(parents=True, exist_ok=True)
        return kb_path / "chunks.jsonl"

    def _iter_chunks(self, kb_id: str):
        chunks_file = self._chunks_file(kb_id)
        if not chunks_file.exists():
            return
        with chunks_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue

    def add_chunks(self, kb_id: str, doc_id: str, chunks: list[dict[str, Any]]) -> None:
        chunks_file = self._chunks_file(kb_id)
        with chunks_file.open("a", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    def search_vector(self, kb_id: str, query_vec: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        q = _normalize(query_vec)
        chunks = list(self._iter_chunks(kb_id))
        if not chunks:
            return []

        scored = []
        for rec in chunks:
            vec = rec.get("embedding", [])
            if not vec:
                continue
            v = _normalize(vec)
            score = float(np.dot(v, q))
            scored.append({
                "id": rec["id"],
                "doc_id": rec.get("doc_id"),
                "text": rec.get("text", ""),
                "score": round(score, 6),
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def search_keyword(self, kb_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        chunks = list(self._iter_chunks(kb_id))
        scorer = KeywordScorer()
        scorer.index(chunks)
        scores = scorer.score(query)

        # Build lookup for text
        by_id = {rec["id"]: rec for rec in chunks}
        results = []
        for chunk_id, score in scores[:top_k]:
            rec = by_id.get(chunk_id)
            if rec:
                results.append({
                    "id": rec["id"],
                    "doc_id": rec.get("doc_id"),
                    "text": rec.get("text", ""),
                    "score": round(score, 6),
                })
        return results

    def delete_kb(self, kb_id: str) -> None:
        import shutil
        kb_path = self.kb_dir / kb_id
        if kb_path.exists():
            shutil.rmtree(kb_path, ignore_errors=True)

    def stats(self, kb_id: str) -> dict[str, Any]:
        chunks = list(self._iter_chunks(kb_id))
        doc_ids = {rec.get("doc_id") for rec in chunks}
        return {
            "backend": "disk",
            "chunk_count": len(chunks),
            "document_count": len(doc_ids),
        }


# === Supabase Vector Store =================================================

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover
    Client = None  # type: ignore
    create_client = None  # type: ignore


class SupabaseVectorStore(VectorStore):
    """Supabase pgvector-backed vector store with Postgres full-text search."""

    def __init__(self, url: str, key: str):
        if create_client is None:
            raise RuntimeError("supabase package not installed")
        self.client: Client = create_client(url, key)

    def add_chunks(self, kb_id: str, doc_id: str, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        rows = []
        for rec in chunks:
            rows.append({
                "kb_id": kb_id,
                "doc_id": doc_id,
                "chunk_index": rec.get("index", 0),
                "text": rec.get("text", ""),
                "embedding": _pad_embedding(rec.get("embedding", [])),
                "metadata": json.dumps(rec.get("metadata", {})),
            })
        # Batch insert in chunks of 100
        for i in range(0, len(rows), 100):
            self.client.table("kb_chunks").insert(rows[i : i + 100]).execute()

    def search_vector(self, kb_id: str, query_vec: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        vec = _pad_embedding(query_vec)
        # Use RPC for vector similarity if available; otherwise raw SQL fallback via rpc
        try:
            response = self.client.rpc(
                "match_kb_chunks",
                {
                    "query_kb_id": kb_id,
                    "query_embedding": vec,
                    "match_count": top_k,
                },
            ).execute()
            results = []
            for row in response.data or []:
                results.append({
                    "id": f"{kb_id}-{row.get('doc_id')}-{row.get('chunk_index')}",
                    "doc_id": row.get("doc_id"),
                    "text": row.get("text", ""),
                    "score": round(float(row.get("similarity", 0)), 6),
                })
            return results
        except Exception:
            # Fallback: select all and compute cosine in Python (fine for small KBs)
            return self._local_vector_search(kb_id, query_vec, top_k)

    def _local_vector_search(self, kb_id: str, query_vec: list[float], top_k: int) -> list[dict[str, Any]]:
        q = _normalize(query_vec)
        response = self.client.table("kb_chunks").select("*").eq("kb_id", kb_id).execute()
        results = []
        for row in response.data or []:
            vec = row.get("embedding", [])
            if not vec:
                continue
            v = _normalize(vec)
            score = float(np.dot(v, q))
            results.append({
                "id": f"{kb_id}-{row.get('doc_id')}-{row.get('chunk_index')}",
                "doc_id": row.get("doc_id"),
                "text": row.get("text", ""),
                "score": round(score, 6),
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_keyword(self, kb_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        try:
            # Try RPC for ranked full-text search
            response = self.client.rpc(
                "search_kb_chunks_fts",
                {
                    "query_kb_id": kb_id,
                    "query_text": query,
                    "match_count": top_k,
                },
            ).execute()
            results = []
            for row in response.data or []:
                results.append({
                    "id": f"{kb_id}-{row.get('doc_id')}-{row.get('chunk_index')}",
                    "doc_id": row.get("doc_id"),
                    "text": row.get("text", ""),
                    "score": round(float(row.get("rank", 0)), 6),
                })
            return results
        except Exception:
            # Fallback: fetch all and score locally
            return self._local_keyword_search(kb_id, query, top_k)

    def _local_keyword_search(self, kb_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
        response = self.client.table("kb_chunks").select("*").eq("kb_id", kb_id).execute()
        chunks = response.data or []
        scorer = KeywordScorer()
        scorer.index(chunks)
        scores = scorer.score(query)
        by_id = {f"{kb_id}-{rec.get('doc_id')}-{rec.get('chunk_index')}": rec for rec in chunks}
        results = []
        for chunk_id, score in scores[:top_k]:
            rec = by_id.get(chunk_id)
            if rec:
                results.append({
                    "id": chunk_id,
                    "doc_id": rec.get("doc_id"),
                    "text": rec.get("text", ""),
                    "score": round(score, 6),
                })
        return results

    def delete_kb(self, kb_id: str) -> None:
        self.client.table("kb_chunks").delete().eq("kb_id", kb_id).execute()

    def stats(self, kb_id: str) -> dict[str, Any]:
        response = self.client.table("kb_chunks").select("*", count="exact").eq("kb_id", kb_id).execute()
        count = response.count if response.count is not None else len(response.data or [])
        doc_ids = {row.get("doc_id") for row in (response.data or [])}
        return {
            "backend": "supabase",
            "chunk_count": count,
            "document_count": len(doc_ids),
        }


# === Factory ===============================================================

def create_vector_store(root: Path, backend: str | None = None) -> VectorStore:
    """Create a vector store. Prefers Supabase if configured."""
    if backend == "supabase" or (backend is None and os.environ.get("SUPABASE_URL")):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        if url and key:
            try:
                return SupabaseVectorStore(url, key)
            except Exception:
                pass
    return DiskVectorStore(root)
