--
-- PostgreSQL database dump
--

\restrict i3NM135PvaiXa0vQkwx6vJnYUNjKzlg0nEus1TwpNFJA1DOC9IAGkT0I66xemmv

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.documents (
    id integer NOT NULL,
    doc_id text NOT NULL,
    title text NOT NULL,
    content text NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english'::regconfig, ((title || ' '::text) || content))) STORED,
    embedding public.vector(384),
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.documents OWNER TO postgres;

--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.documents_id_seq OWNER TO postgres;

--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- Name: documents documents_doc_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_doc_id_key UNIQUE (doc_id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: idx_docs_embedding; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_docs_embedding ON public.documents USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_docs_tsv; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_docs_tsv ON public.documents USING gin (tsv);


--
-- PostgreSQL database dump complete
--

\unrestrict i3NM135PvaiXa0vQkwx6vJnYUNjKzlg0nEus1TwpNFJA1DOC9IAGkT0I66xemmv

