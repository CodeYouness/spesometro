# 0003 — NiceGUI 4.0 adottato con accettazione del rischio

**Contesto:** NiceGUI 4.0.0 è uscito pochi giorni prima dell'inizio del progetto (rischio 13 in SPEC §11); al 7/11 nessuna issue aperta su `run_with`, auth, proxy, Tailwind o `httpx2`.
**Decisione:** NiceGUI 4.0.0 è la versione di riferimento, pinnata esatta; nessuna 3.x come fallback; regole di codice 4.0 in `CLAUDE.md`.
**Conseguenze:** test Playwright sulle pagine critiche (revisione, approvazione) in S2; su bug bloccante documentato: nuovo ADR + pin a `3.19.0` (costo ~mezza giornata), non prima.
