# Backlog

Fonte di verità versionata. I ticket di dettaglio stanno in `.scratch/s1/issues/` e `.scratch/s2/issues/` (non in git).

## S1

Allineato alla SPEC v1.4 (9/11). Ordine di dipendenza: 01 → 02, 03, 05, 06 → 07 → 08 → 09.

| #  | Titolo                                                      | Stima | Stato           | Bloccato da    |
|----|-------------------------------------------------------------|-------|-----------------|----------------|
| 01 | Scaffold monorepo e deploy "hello" su Railway EU            | 4 h   | fatto (19/11)   | —              |
| 02 | Schema dati v1.4 (gruppi, `Flyer`, provenienza), Alembic    | 3,5 h | fatto (19/11)   | 01             |
| 03 | Login lato server con Supabase Auth in NiceGUI              | 1,5 h | ready-for-agent | 01             |
| 05 | Minimizzazione: ridimensionamento e redazione del JSON      | 1 h   | ready-for-agent | 01             |
| 06 | Schemi di estrazione, formato del golden set e scorer       | 1,5 h | ready-for-agent | 01             |
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
