# Backlog

Fonte di verità versionata. I ticket di dettaglio stanno in `.scratch/s1/issues/` (non in git).

## S1

Ordine di dipendenza: 01 → 02, 03, 05, 06 → 04, 07 → 08 → 09.

| #  | Titolo                                                      | Stima | Stato           | Bloccato da    |
|----|-------------------------------------------------------------|-------|-----------------|----------------|
| 01 | Scaffold monorepo e deploy "hello" su Railway EU            | 4 h   | ready-for-agent | —              |
| 02 | Schema dati, Alembic async e mixin provenienza su Supabase  | 3 h   | ready-for-agent | 01             |
| 03 | Verifica token Supabase Auth via JWKS in FastAPI            | 1,5 h | ready-for-agent | 01             |
| 05 | Minimizzazione immagini in packages/core                    | 1,5 h | ready-for-agent | 01             |
| 06 | Schemi di estrazione, formato del golden set e scorer       | 1,5 h | ready-for-agent | 01             |
| 04 | Backup giornaliero cifrato su Cloudflare R2 + keep-alive    | 2 h   | ready-for-agent | 02             |
| 07 | Annotazione del golden set S1                               | 3 h   | ready-for-human | 06             |
| 08 | Estrazione scontrini con Provider e guardrail somma/totale  | 3 h   | ready-for-agent | 05, 06, 07     |
| 09 | Estrazione volantini e gate di precision S1                 | 3 h   | ready-for-agent | 06, 07, 08     |

Totale stimato: 22,5 h (prerequisiti umani esclusi).
