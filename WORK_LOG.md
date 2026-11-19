# Work log

| Data | Ticket | Ore stimate | Ore reali | Note |
|---|---|---|---|---|
| 2026-11-09 | Revisione della spec → v1.4 (nessun ticket) | — | — | SPEC, ADR 0005–0012, glossario, CLAUDE.md, ticket S1 e backlog riallineati |
| 2026-11-19 | S1-01 Scaffold monorepo e deploy "hello" | 4 h | ~1 h | Online su Railway EU West (1 replica, sleeping spento), CI verde. Config migrata a `.railway/railway.ts` (ADR 0013), healthcheck `/health` attivo. Aperti: GHCR, gitleaks in CI |
| 2026-11-19 | S1-02 Schema dati v1.4, Alembic async, provenienza (ticket 01–05 di `schema-dati`) | 3 h 45 min | ~0,7 h | `packages/db`, 12 tabelle + vista `price_observation` in una migrazione, FK composte per utente; 33 test + 45 integration verdi. Resta il ticket 06 (verifica su Supabase, umano) |
