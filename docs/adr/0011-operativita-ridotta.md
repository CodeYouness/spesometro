# 0011 — Operatività ridotta

**Contesto:** backup completo giornaliero (roles, `auth`, Storage), keep-alive, VPS da ordinare entro il 15/11 e deploy automatico fino alla consegna erano sproporzionati per due utenti, di cui uno sintetico, e mettevano a rischio la finestra di valutazione.
**Decisione:** backup settimanale del solo schema `public`, cifrato con `age` su R2, più un run manuale prima del freeze; nessun keep-alive dedicato; VPS d'apprendimento solo dopo la consegna; deploy automatico spento dal 3/12, ultimo deploy di funzionalità il 2/12; credenziali demo nel documento di consegna; nel repo pubblico solo annotazioni, cassette vcrpy su immagini sintetiche.
**Conseguenze:** il ticket 04 si riduce e passa in S2; il test di ripristino resta entro il 25/11; `make eval` completo richiede i dati privati, nel repo restano i report e alcuni scontrini sintetici.
**Precisazione (25/11):** "nessun dato reale nel repo pubblico" riguarda immagini e contenuti grezzi (foto, PDF, cassette). Le annotazioni del golden set, anche degli scontrini reali, stanno nel repo come da SPEC §5: scelta confermata sapendo che contengono catena, data, ora, totale e acquisti.
