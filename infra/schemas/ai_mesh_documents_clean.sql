-- PostgreSQL 16 ai_mesh database schema
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.documents (
    id SERIAL PRIMARY KEY,
    doc_id text NOT NULL UNIQUE,
    title text NOT NULL,
    content text NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, ((title || ' '::text) || content))) STORED,
    embedding public.vector(384),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_docs_tsv ON public.documents USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_docs_embedding ON public.documents USING hnsw (embedding public.vector_cosine_ops);
