# 0010 — Matching: trigrammi prima degli embedding

**Contesto:** la v1.3 prevedeva ricerca ibrida "BM25" (full-text Postgres) + embedding con indice HNSW. Il full-text di Postgres non è BM25 e rende poco sulle righe abbreviate degli scontrini; con 100–150 prodotti un indice HNSW non serve.
**Decisione:** alias confermati → similarità a trigrammi (`pg_trgm`) → LLM sui primi 10 → coda di revisione. Gli embedding si aggiungono solo se l'F1 sul golden set resta sotto l'obiettivo, a scansione esatta e senza HNSW.
**Conseguenze:** OpenAI non è necessario in S1–S2; per il RAG della chat il provider degli embedding si decide con una riga di ADR quando la chat parte.
