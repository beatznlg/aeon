"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type KB = {
  id: string;
  name: string;
  description: string;
  chunk_size: number;
  overlap: number;
  document_count: number;
  chunk_count: number;
};

type Chunk = {
  id: string;
  doc_id: string;
  text: string;
  score: number;
  vector_rank?: number | null;
  keyword_rank?: number | null;
  rrf_score?: number;
};

type KBStats = {
  backend: string;
  chunk_count: number;
  document_count: number;
};

export default function KnowledgePageClient() {
  const [kbs, setKbs] = useState<KB[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [chunkSize, setChunkSize] = useState(512);
  const [overlap, setOverlap] = useState(64);

  const [selectedKb, setSelectedKb] = useState<string>("");
  const [docId, setDocId] = useState("");
  const [docText, setDocText] = useState("");
  const [docFile, setDocFile] = useState<File | null>(null);
  const [uploadMode, setUploadMode] = useState<"text" | "file">("text");
  const [uploadResult, setUploadResult] = useState<{ doc_id: string; chunks: number; preview?: any[] } | null>(null);
  const [showPreview, setShowPreview] = useState(false);

  const [query, setQuery] = useState("");
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [querying, setQuerying] = useState(false);
  const [mode, setMode] = useState<"hybrid" | "vector" | "keyword">("hybrid");
  const [topK, setTopK] = useState(5);
  const [stats, setStats] = useState<Record<string, KBStats>>({});

  useEffect(() => {
    fetchKbs();
  }, []);

  useEffect(() => {
    kbs.forEach((k) => {
      fetch(`/api/os/ai/knowledge-bases/${k.id}/query`, { cache: "no-store" })
        .then((r) => r.json())
        .then((data) => {
          if (data.ok) setStats((prev) => ({ ...prev, [k.id]: data.stats }));
        })
        .catch(() => null);
    });
  }, [kbs]);

  const fetchKbs = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/os/ai/knowledge-bases", { cache: "no-store" });
      const data = await res.json();
      if (data.ok) {
        setKbs(data.knowledge_bases || []);
      } else {
        setError(data.error || "failed to load knowledge bases");
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  const createKb = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/os/ai/knowledge-bases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description, chunk_size: chunkSize, overlap }),
      });
      const data = await res.json();
      if (data.ok) {
        setKbs((prev) => [data.knowledge_base, ...prev]);
        setName("");
        setDescription("");
      } else {
        setError(data.error || "failed to create knowledge base");
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  const uploadDoc = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedKb) return;
    setUploadResult(null);
    setError(null);

    let text = docText;
    let fileName = "";

    if (uploadMode === "file" && docFile) {
      text = await docFile.text();
      fileName = docFile.name;
    }

    if (!text.trim()) {
      setError("Document text is empty");
      return;
    }

    try {
      const res = await fetch(`/api/os/ai/knowledge-bases/${selectedKb}/documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_id: docId || undefined,
          text: text,
          metadata: { file_name: fileName, preview: true },
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setUploadResult(data);
        setDocText("");
        setDocId("");
        setDocFile(null);
        fetchKbs();
      } else {
        setError(data.error || "failed to upload document");
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  const runQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedKb) return;
    setQuerying(true);
    try {
      const res = await fetch(`/api/os/ai/knowledge-bases/${selectedKb}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: topK, mode }),
      });
      const data = await res.json();
      if (data.ok) setChunks(data.chunks || []);
      else setError(data.error || "query failed");
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setQuerying(false);
    }
  };

  const deleteKb = async (id: string) => {
    if (!confirm("Delete this knowledge base?")) return;
    try {
      const res = await fetch(`/api/os/ai/knowledge-bases/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (data.ok) setKbs((prev) => prev.filter((k) => k.id !== id));
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1 style={{ background: "var(--grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            Knowledge Bases
          </h1>
          <p className="dashboard-subtitle">Upload documents, manage chunks, and test RAG retrieval</p>
        </div>
        <Link href="/os" className="btn btn-secondary">← OS Launcher</Link>
      </header>

      {error && <div className="module-alert danger">{error}</div>}

      <section className="os-card" style={{ marginBottom: 24 }}>
        <h3>Create Knowledge Base</h3>
        <form onSubmit={createKb} className="form-grid">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Description
            <input value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <label>
            Chunk size
            <input type="number" value={chunkSize} onChange={(e) => setChunkSize(Number(e.target.value))} />
          </label>
          <label>
            Overlap
            <input type="number" value={overlap} onChange={(e) => setOverlap(Number(e.target.value))} />
          </label>
          <button type="submit" className="btn btn-primary">Create</button>
        </form>
      </section>

      <section className="os-card" style={{ marginBottom: 24 }}>
        <h3>Upload Document</h3>
        <form onSubmit={uploadDoc} className="form-grid">
          <label>
            Knowledge Base
            <select value={selectedKb} onChange={(e) => setSelectedKb(e.target.value)}>
              <option value="">Select…</option>
              {kbs.map((k) => (
                <option key={k.id} value={k.id}>{k.name}</option>
              ))}
            </select>
          </label>
          <label>
            Document ID (optional)
            <input value={docId} onChange={(e) => setDocId(e.target.value)} placeholder="auto-generated" />
          </label>
          <div className="upload-mode-toggle">
            <button type="button" className={`btn btn-sm ${uploadMode === "text" ? "btn-primary" : ""}`} onClick={() => setUploadMode("text")}>
              Paste Text
            </button>
            <button type="button" className={`btn btn-sm ${uploadMode === "file" ? "btn-primary" : ""}`} onClick={() => setUploadMode("file")}>
              Upload File
            </button>
          </div>
          {uploadMode === "text" ? (
            <label className="span-2">
              Document text
              <textarea value={docText} onChange={(e) => setDocText(e.target.value)} rows={6} />
            </label>
          ) : (
            <label className="span-2">
              File (txt, md, csv, json)
              <input type="file" accept=".txt,.md,.csv,.json,.py,.js,.ts,.jsx,.tsx" onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) setDocFile(file);
              }} />
              {docFile && <p style={{ marginTop: 4, fontSize: "0.8rem", color: "var(--fg-soft)" }}>{docFile.name} ({(docFile.size / 1024).toFixed(1)} KB)</p>}
            </label>
          )}
          <button type="submit" className="btn btn-primary" disabled={uploadMode === "file" && !docFile}>
            Upload & Chunk
          </button>
        </form>

        {uploadResult && (
          <div className="upload-result" style={{ marginTop: 16 }}>
            <div className="module-alert" style={{ borderLeft: "3px solid #22c55e", color: "#22c55e" }}>
              Document uploaded — {uploadResult.chunks} chunks created
            </div>
            {uploadResult.preview && uploadResult.preview.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <button className="btn btn-sm" onClick={() => setShowPreview(!showPreview)}>
                  {showPreview ? "Hide" : "Show"} Chunk Preview ({uploadResult.preview.length})
                </button>
                {showPreview && (
                  <div className="chunk-preview-list" style={{ marginTop: 8 }}>
                    {uploadResult.preview.map((chunk: any, i: number) => (
                      <div key={i} className="chunk-preview-item">
                        <div className="chunk-preview-header">Chunk #{chunk.index}</div>
                        <div className="chunk-preview-text">{chunk.text}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="os-card" style={{ marginBottom: 24 }}>
        <h3>Test Retrieval</h3>
        <form onSubmit={runQuery} className="form-grid">
          <label className="span-2">
            Query
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask something about the uploaded documents…" required />
          </label>
          <label>
            Search mode
            <select value={mode} onChange={(e) => setMode(e.target.value as any)}>
              <option value="hybrid">Hybrid (RRF)</option>
              <option value="vector">Vector only</option>
              <option value="keyword">Keyword only</option>
            </select>
          </label>
          <label>
            Top-K
            <input type="number" min={1} max={20} value={topK} onChange={(e) => setTopK(Number(e.target.value))} />
          </label>
          <button type="submit" className="btn btn-primary" disabled={querying}>{querying ? "Querying…" : "Retrieve"}</button>
        </form>
        {chunks.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4>Top chunks</h4>
            {chunks.map((c) => (
              <div key={c.id} className="os-card" style={{ marginBottom: 8 }}>
                <div className="os-card-header">
                  <span className="os-status-pill active">{c.doc_id}</span>
                  <span className="os-status-pill active">score {c.rrf_score ?? c.score}</span>
                  {typeof c.vector_rank === "number" && <span className="os-status-pill active">v-rank {c.vector_rank}</span>}
                  {typeof c.keyword_rank === "number" && <span className="os-status-pill active">k-rank {c.keyword_rank}</span>}
                </div>
                <p className="os-desc">{c.text}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3>Knowledge Bases ({kbs.length})</h3>
        {loading ? (
          <p style={{ color: "var(--fg-mute)" }}>Loading…</p>
        ) : kbs.length === 0 ? (
          <p style={{ color: "var(--fg-mute)" }}>No knowledge bases yet.</p>
        ) : (
          <div className="os-grid">
            {kbs.map((k) => (
              <div key={k.id} className="os-card">
                <div className="os-card-header">
                  <h4>{k.name}</h4>
                  <span className="os-status-pill active">{k.document_count} docs</span>
                </div>
                <p className="os-desc">{k.description || "No description"}</p>
                <p className="os-desc">Chunks: {k.chunk_count}</p>
                {stats[k.id] && (
                  <p className="os-desc">
                    Backend: <strong>{stats[k.id].backend}</strong> · Docs: {stats[k.id].document_count} · Chunks: {stats[k.id].chunk_count}
                  </p>
                )}
                <button className="btn btn-sm" onClick={() => deleteKb(k.id)}>Delete</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
