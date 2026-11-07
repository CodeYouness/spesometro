# 0002 — Nessun modello uscito da meno di 30 giorni in produzione d'esame

**Contesto:** l'app deve restare affidabile nella finestra di valutazione 5–12 dicembre 2026; i modelli appena rilasciati non hanno storico di affidabilità.
**Decisione:** nessun modello uscito da meno di 30 giorni va in produzione d'esame: va nell'eval. Versioni dei modelli pinnate esplicitamente, mai `-latest`.
**Conseguenze:** un modello nuovo può diventare default solo dopo 30 giorni e solo se batte il default sul golden set, con motivazione nel README.
