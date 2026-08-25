-- AEON OS Phase 7: Vector store + hybrid search
-- Run after 0001_workspace_rbac.sql.

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

-- Chunks table for knowledge base vector persistence
CREATE TABLE IF NOT EXISTS public.kb_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kb_id TEXT NOT NULL,
  doc_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  embedding vector(1536) NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (kb_id, doc_id, chunk_index)
);

-- Indexes for fast hybrid search
CREATE INDEX IF NOT EXISTS idx_kb_chunks_kb_id ON public.kb_chunks (kb_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_id ON public.kb_chunks (doc_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding ON public.kb_chunks
  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_fts ON public.kb_chunks
  USING GIN (to_tsvector('english', text));

-- Row Level Security
ALTER TABLE public.kb_chunks ENABLE ROW LEVEL SECURITY;

-- (GRANTs for the RPC functions live at the bottom of this file, after the
-- functions are created — Postgres cannot grant execute on a function that
-- does not exist yet.)
DROP POLICY IF EXISTS kb_chunks_select ON public.kb_chunks;
CREATE POLICY kb_chunks_select ON public.kb_chunks
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.memberships m
      JOIN public.workspaces w ON w.id = m.workspace_id
      WHERE w.slug = kb_chunks.kb_id AND m.user_id = auth.uid()
    )
  );

-- Vector similarity RPC for pgvector
CREATE OR REPLACE FUNCTION public.match_kb_chunks(
  query_kb_id TEXT,
  query_embedding VECTOR(1536),
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  doc_id TEXT,
  chunk_index INT,
  text TEXT,
  similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    c.doc_id,
    c.chunk_index,
    c.text,
    1 - (c.embedding <=> query_embedding) AS similarity
  FROM public.kb_chunks c
  WHERE c.kb_id = query_kb_id
  ORDER BY c.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- Full-text search RPC
CREATE OR REPLACE FUNCTION public.search_kb_chunks_fts(
  query_kb_id TEXT,
  query_text TEXT,
  match_count INT DEFAULT 5
)
RETURNS TABLE (
  doc_id TEXT,
  chunk_index INT,
  text TEXT,
  rank FLOAT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    c.doc_id,
    c.chunk_index,
    c.text,
    ts_rank(to_tsvector('english', c.text), plainto_tsquery('english', query_text))::FLOAT AS rank
  FROM public.kb_chunks c
  WHERE c.kb_id = query_kb_id
    AND to_tsvector('english', c.text) @@ plainto_tsquery('english', query_text)
  ORDER BY rank DESC
  LIMIT match_count;
$$;

-- Allow the anon/service roles to call the RPCs (must come after creation)
GRANT EXECUTE ON FUNCTION public.match_kb_chunks(TEXT, VECTOR(1536), INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.match_kb_chunks(TEXT, VECTOR(1536), INT) TO anon;
GRANT EXECUTE ON FUNCTION public.search_kb_chunks_fts(TEXT, TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_kb_chunks_fts(TEXT, TEXT, INT) TO anon;
