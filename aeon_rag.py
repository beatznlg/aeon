"""
AEON OS Phase 6 — Advanced AI Orchestration & RAG
====================================================
Lightweight prompt registry, knowledge base manager, and RAG retriever.

Usage:
    from aeon_rag import PromptRegistry, KnowledgeBaseManager, RAGOrchestrator
    pr = PromptRegistry(root)
    pr.save_prompt({"name": "support", "template": "Answer {{question}}"})

    kbm = KnowledgeBaseManager(root)
    kb = kbm.create_kb({"name": "docs"})
    kbm.add_document(kb["id"], "doc1", "AEON is an AI OS...")
    chunks = kbm.query(kb["id"], "What is AEON?", top_k=3)

    rag = RAGOrchestrator(root)
    answer = rag.chat(kb_id, prompt_id, {"question": "What is AEON?"})
"""

import os
import re
import json
import time
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict

import numpy as np
import requests

from aeon_llm import get_llm_provider


# === helpers ==============================================================

def _generate_id() -> str:
    return secrets.token_urlsafe(8)


def _now() -> float:
    return time.time()


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "-", name.lower()).strip("-")[:50]


def _render_template(template: str, variables: Dict[str, Any]) -> str:
    """Simple {{var}} templating."""
    def repl(m):
        key = m.group(1).strip()
        return str(variables.get(key, ""))
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", repl, template)


def _chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    """Split text into overlapping chunks by sentences, falling back to words."""
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    # Split into sentences (simple heuristic)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s for s in sentences if s]

    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= chunk_size:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            current = s

        # Overlap: keep last `overlap` chars if chunk is large enough
        if len(current) >= chunk_size:
            chunks.append(current)
            overlap_text = current[-overlap:] if len(current) > overlap else current
            current = overlap_text

    if current and (not chunks or current != chunks[-1]):
        chunks.append(current)

    # Fallback word-level if a single sentence is longer than chunk_size
    refined = []
    for c in chunks:
        if len(c) <= chunk_size:
            refined.append(c)
            continue
        words = c.split()
        part = ""
        for w in words:
            if len(part) + len(w) + 1 > chunk_size:
                refined.append(part.strip())
                part = w
            else:
                part = (part + " " + w).strip()
        if part:
            refined.append(part)
    return refined or [text[:chunk_size]]


# === Embedding backends ===================================================

class Embedder:
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError


class StubEmbedder(Embedder):
    """Deterministic hash-based random projection. Not semantic, but zero-deps."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        out = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)
            rng = np.random.default_rng(seed)
            vec = rng.normal(0, 1, self.dim).astype(np.float32)
            vec = vec / (np.linalg.norm(vec) + 1e-9)
            out.append(vec.tolist())
        return out


class OpenAIEmbedder(Embedder):
    def __init__(self, api_key: str = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not configured")
        r = requests.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]


class HFEmbedder(Embedder):
    """Hugging Face Inference API embeddings."""

    def __init__(self, token: str = None, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.token = token or os.environ.get("HUGGINGFACE_TOKEN")
        self.model = model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.token:
            raise RuntimeError("HuggingFace token not configured")
        r = requests.post(
            f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"inputs": texts, "options": {"wait_for_model": True}},
            timeout=90,
        )
        r.raise_for_status()
        return r.json()


def get_embedder(preferred: str = None) -> Embedder:
    """Return best available embedder."""
    if preferred == "openai" or (preferred is None and os.environ.get("OPENAI_API_KEY")):
        try:
            return OpenAIEmbedder()
        except Exception:
            pass
    if preferred == "hf" or (preferred is None and os.environ.get("HUGGINGFACE_TOKEN")):
        try:
            return HFEmbedder()
        except Exception:
            pass
    return StubEmbedder()


# === Prompt Registry ======================================================

@dataclass
class PromptTemplate:
    id: str
    name: str
    template: str
    system: str
    variables: List[str]
    provider: str
    model: str
    tags: List[str]
    version: int
    created_at: float
    updated_at: float

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PromptRegistry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.prompts_dir = self.root / "prompts"
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.prompts_dir / "index.json"
        self._index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        if self.index_file.exists():
            try:
                return json.loads(self.index_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_index(self):
        self.index_file.write_text(json.dumps(self._index, indent=2, ensure_ascii=False), encoding="utf-8")

    def _extract_vars(self, template: str) -> List[str]:
        return sorted(set(re.findall(r"\{\{\s*(\w+)\s*\}\}", template)))

    def save_prompt(self, data: Dict[str, Any]) -> PromptTemplate:
        prompt_id = data.get("id") or _slugify(data.get("name", "untitled")) or _generate_id()
        existing = self._index.get(prompt_id)
        version = 1
        if existing:
            version = existing.get("version", 1) + 1

        template = data.get("template", "")
        prompt = PromptTemplate(
            id=prompt_id,
            name=data.get("name", "Untitled"),
            template=template,
            system=data.get("system", ""),
            variables=self._extract_vars(template),
            provider=data.get("provider", "openrouter"),
            model=data.get("model", ""),
            tags=data.get("tags", []),
            version=version,
            created_at=existing.get("created_at") if existing else _now(),
            updated_at=_now(),
        )

        prompt_dir = self.prompts_dir / prompt_id
        prompt_dir.mkdir(parents=True, exist_ok=True)
        version_file = prompt_dir / f"v{version}.json"
        version_file.write_text(json.dumps(prompt.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        self._index[prompt_id] = {
            "id": prompt_id,
            "name": prompt.name,
            "version": version,
            "created_at": prompt.created_at,
            "updated_at": prompt.updated_at,
        }
        self._save_index()
        return prompt

    def get_prompt(self, prompt_id: str) -> Optional[PromptTemplate]:
        entry = self._index.get(prompt_id)
        if not entry:
            return None
        version = entry.get("version", 1)
        version_file = self.prompts_dir / prompt_id / f"v{version}.json"
        if not version_file.exists():
            return None
        try:
            return PromptTemplate.from_dict(json.loads(version_file.read_text(encoding="utf-8")))
        except Exception:
            return None

    def delete_prompt(self, prompt_id: str) -> bool:
        if prompt_id not in self._index:
            return False
        del self._index[prompt_id]
        self._save_index()
        return True

    def list_prompts(self) -> List[Dict[str, Any]]:
        return list(self._index.values())

    def render(self, prompt_id: str, variables: Dict[str, Any]) -> Tuple[str, str]:
        prompt = self.get_prompt(prompt_id)
        if not prompt:
            return "", ""
        return _render_template(prompt.template, variables), _render_template(prompt.system, variables)


# === Knowledge Base Manager ===============================================

@dataclass
class KnowledgeBase:
    id: str
    name: str
    description: str
    chunk_size: int
    overlap: int
    embedding_provider: str
    created_at: float
    document_count: int = 0
    chunk_count: int = 0

    def to_dict(self):
        return asdict(self)


class KnowledgeBaseManager:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.kb_dir = self.root / "knowledge_bases"
        self.kb_dir.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        if (self.kb_dir / "index.json").exists():
            try:
                return json.loads((self.kb_dir / "index.json").read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_index(self):
        (self.kb_dir / "index.json").write_text(json.dumps(self._index, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_kb(self, data: Dict[str, Any]) -> KnowledgeBase:
        kb_id = data.get("id") or _slugify(data.get("name", "kb")) or _generate_id()
        kb = KnowledgeBase(
            id=kb_id,
            name=data.get("name", "Untitled KB"),
            description=data.get("description", ""),
            chunk_size=int(data.get("chunk_size", 512)),
            overlap=int(data.get("overlap", 64)),
            embedding_provider=data.get("embedding_provider", "auto"),
            created_at=_now(),
        )
        kb_dir = self.kb_dir / kb_id
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "documents.jsonl").touch(exist_ok=True)
        (kb_dir / "chunks.jsonl").touch(exist_ok=True)
        self._index[kb_id] = kb.to_dict()
        self._save_index()
        return kb

    def get_kb(self, kb_id: str) -> Optional[KnowledgeBase]:
        entry = self._index.get(kb_id)
        if not entry:
            return None
        return KnowledgeBase(**entry)

    def delete_kb(self, kb_id: str) -> bool:
        if kb_id not in self._index:
            return False
        import shutil
        shutil.rmtree(self.kb_dir / kb_id, ignore_errors=True)
        del self._index[kb_id]
        self._save_index()
        return True

    def list_kbs(self) -> List[Dict[str, Any]]:
        return list(self._index.values())

    def add_document(self, kb_id: str, doc_id: str, text: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        kb = self.get_kb(kb_id)
        if not kb:
            raise ValueError("knowledge base not found")

        kb_dir = self.kb_dir / kb_id
        chunks = _chunk_text(text, chunk_size=kb.chunk_size, overlap=kb.overlap)
        embedder = get_embedder(kb.embedding_provider)
        embeddings = embedder.embed(chunks)

        doc_record = {
            "doc_id": doc_id,
            "kb_id": kb_id,
            "text_length": len(text),
            "chunk_count": len(chunks),
            "metadata": metadata or {},
            "created_at": _now(),
        }
        with (kb_dir / "documents.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(doc_record, ensure_ascii=False) + "\n")

        chunk_records = []
        with (kb_dir / "chunks.jsonl").open("a", encoding="utf-8") as f:
            for i, (chunk_text, vec) in enumerate(zip(chunks, embeddings)):
                rec = {
                    "id": _generate_id(),
                    "doc_id": doc_id,
                    "kb_id": kb_id,
                    "index": i,
                    "text": chunk_text,
                    "embedding": vec,
                    "created_at": _now(),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                chunk_records.append(rec)

        # Update stats
        self._index[kb_id]["document_count"] = self._index[kb_id].get("document_count", 0) + 1
        self._index[kb_id]["chunk_count"] = self._index[kb_id].get("chunk_count", 0) + len(chunks)
        self._save_index()
        return {"doc_id": doc_id, "chunks": len(chunk_records)}

    def _iter_chunks(self, kb_id: str):
        chunks_file = self.kb_dir / kb_id / "chunks.jsonl"
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

    def query(self, kb_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        kb = self.get_kb(kb_id)
        if not kb:
            raise ValueError("knowledge base not found")

        embedder = get_embedder(kb.embedding_provider)
        query_vec = embedder.embed([query])[0]
        q = np.array(query_vec, dtype=np.float32)

        chunks = list(self._iter_chunks(kb_id))
        if not chunks:
            return []

        # Cosine similarity
        scored = []
        for rec in chunks:
            vec = np.array(rec.get("embedding", []), dtype=np.float32)
            if vec.size == 0:
                continue
            norm = np.linalg.norm(vec) * np.linalg.norm(q)
            score = float(np.dot(vec, q) / (norm + 1e-9))
            scored.append({"score": score, "chunk": rec})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return [
            {
                "id": s["chunk"]["id"],
                "doc_id": s["chunk"]["doc_id"],
                "text": s["chunk"]["text"],
                "score": round(s["score"], 4),
            }
            for s in scored[:top_k]
        ]


# === RAG Orchestrator =====================================================

class RAGOrchestrator:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.prompts = PromptRegistry(root)
        self.kbs = KnowledgeBaseManager(root)

    def chat(self, kb_id: Optional[str], prompt_id: Optional[str], variables: Dict[str, Any], query: str, top_k: int = 5) -> Dict[str, Any]:
        """Render a prompt, retrieve context, call LLM."""
        # Retrieve context
        context_chunks = []
        if kb_id:
            context_chunks = self.kbs.query(kb_id, query, top_k=top_k)

        context_text = "\n\n".join([f"[doc {c['doc_id']}] {c['text']}" for c in context_chunks])

        # Determine prompt text
        prompt_text = query
        system_text = "You are AEON, an autonomous AI operating system. Answer using the provided context if available."
        if prompt_id:
            rendered, rendered_system = self.prompts.render(prompt_id, variables)
            if rendered:
                prompt_text = _render_template(rendered, {"query": query, "context": context_text, **variables})
            if rendered_system:
                system_text = _render_template(rendered_system, {"query": query, "context": context_text, **variables})
        elif context_text:
            prompt_text = f"Context:\n{context_text}\n\nQuestion: {query}\nAnswer:"

        # Call LLM
        provider = get_llm_provider()
        out = provider.generate(prompt_text, system=system_text, max_new_tokens=512)
        return {
            "ok": True,
            "answer": out.get("text", ""),
            "backend": out.get("backend", "unknown"),
            "tokens_used": out.get("tokens_used", 0),
            "context_chunks": context_chunks,
        }

    def list_prompts(self) -> List[Dict[str, Any]]:
        return self.prompts.list_prompts()

    def list_kbs(self) -> List[Dict[str, Any]]:
        return self.kbs.list_kbs()
