# Backlog

Fonte di verità versionata. I ticket di dettaglio stanno in `.scratch/s1/issues/` e `.scratch/s2/issues/` (non in git).

## S1

Allineato alla SPEC v1.4 (9/11). Ordine di dipendenza: 01 → 02, 03, 05, 06 → 07 → 08 → 09.

| #  | Titolo                                                      | Stima | Stato           | Bloccato da    |
|----|-------------------------------------------------------------|-------|-----------------|----------------|
| 01 | Scaffold monorepo e deploy "hello" su Railway EU            | 4 h   | fatto (19/11)   | —              |
| 02 | Schema dati v1.4 (gruppi, `Flyer`, provenienza), Alembic    | 3,5 h | fatto (19/11)   | 01             |
| 03 | Login lato server con Supabase Auth in NiceGUI              | 1,5 h | fatto (25/11)   | 01             |
| 05 | Minimizzazione: ridimensionamento e redazione del JSON      | 1 h   | fatto (26/11)   | 01             |
| 06 | Schemi di estrazione, formato del golden set e scorer       | 1,5 h | fatto (25/11)   | 01             |
| 07 | Annotazione del golden set S1                               | 3 h   | ready-for-human | 06             |
| 08 | Estrazione scontrini con Provider e guardrail somma/totale  | 3 h   | ready-for-agent | 05, 06, 07     |
| 09 | Estrazione volantini e gate di precision S1                 | 3 h   | ready-for-agent | 06, 07, 08     |

Totale stimato: 20,5 h (17,5 h di agente + 3 h umane; prerequisiti umani esclusi).

## S2

Primi due ticket; gli altri si generano dalla SPEC v1.4 §9. Gate: fetta verticale online entro il 22/11.

| #  | Titolo                                                      | Stima | Stato           | Bloccato da    |
|----|-------------------------------------------------------------|-------|-----------------|----------------|
| 10 | Salvataggio scontrino: upload → `Job` → DB con deduplica    | 3 h   | ready-for-agent | 02, 03, 08     |
| 04 | Backup settimanale ridotto su Cloudflare R2                 | 1 h   | ready-for-agent | 02             |

## Facoltativi

Fuori calendario: si fanno solo se avanza tempo, senza deploy (SPEC §3.2, colonne extra dell'eval).

- **Colonna LlamaExtract nell'eval** (valutato il 25/11). Servizio ospitato di LlamaIndex: accetta gli schemi del ticket 06 come JSON Schema e restituisce confidenza e citazione per campo. Piano gratuito: 10.000 crediti al mese, circa 400 pagine con estrazione in modalità Agentic. Solo eval, mai produzione: il modello dietro al servizio non è dichiarato né pinnabile (ADR 0002, ADR 0012). Secondo uso: terza prova sul gate dei volantini (ticket 09) se la precision resta sotto il 70% anche con OCR 4.1, prima dell'inserimento assistito. Condizioni: regione UE (`api.cloud.eu.llamaindex.ai`), cache spenta, client su `httpx` e non `httpx2`. Da verificare prima: supporto WEBP (i volantini raccolti sono in WEBP), limiti e prezzi sul sito.
