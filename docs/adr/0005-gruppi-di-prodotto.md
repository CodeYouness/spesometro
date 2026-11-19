# 0005 — Gruppi di prodotto al posto delle equivalenze a coppie

**Contesto:** in v1.3 consumo e magazzino erano agganciati al `Product` e le equivalenze erano coppie (`ProductEquivalence`). Lo stesso bisogno comprato in due catene restava in due `InventoryItem` a livello 0; le coppie non sono transitive; `identico` duplicava `ProductAlias`; Lidl ed Eurospin vendono quasi solo marche proprie, quindi tra catene quasi tutto è "equivalente".
**Decisione:** nuova entità `ProductGroup` (il bisogno) con `Product.group_id`; magazzino, lista e confronto prezzi lavorano sul gruppo, in `unità_base`. `equivalente` = stesso gruppo. `GroupAlternative` collega due gruppi, solo da conferma umana. `ProductEquivalence` e `identico` sono rimossi. `tipo_durata` sta sul gruppo; gli `attributi` per le esclusioni sul `Product`.
**Conseguenze:** il ticket 02 crea lo schema già così; la coda di revisione conferma anche gruppo e attributi; il golden set del matching etichetta "stesso gruppo sì/no".
