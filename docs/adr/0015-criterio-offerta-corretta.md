# 0015 — Criterio di offerta corretta per il gate di precision

**Contesto:** il gate di S1 (precision volantini ≥ 70%, SPEC §3.2) non diceva quando un'offerta estratta conta come corretta. Con "tutti i campi uguali" una data di validità sbagliata boccia un'offerta dal prezzo giusto; con una tolleranza sui prezzi si perdona proprio l'errore che il progetto teme di più, la cifra inventata.
**Decisione:** un'offerta è corretta se, nella stessa pagina, si accoppia uno a uno con un'offerta annotata per `prezzo_confezione` identico al centesimo e nome normalizzato simile sopra una soglia (parametro esplicito, default 0,6). Questo criterio decide il gate. Il criterio severo (tutti i campi uguali) è riportato accanto, solo informativo. Le pagine del golden set si annotano per intero.
**Conseguenze:** il report mostra sempre le due colonne; la soglia di somiglianza è scritta nel report; cambiare criterio dopo aver visto i risultati richiede una nuova ADR.
