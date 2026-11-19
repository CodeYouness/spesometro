"""Insiemi chiusi di valori del dominio (ADR 0014).

Fonte unica: il pacchetto del database li usa per generare i CHECK.
"""

from enum import StrEnum


class Catena(StrEnum):
    LIDL = "lidl"
    EUROSPIN = "eurospin"
    COOP = "coop"
    ALTRA = "altra"


class Attributo(StrEnum):
    MAIALE = "maiale"
    CARNE = "carne"
    PESCE = "pesce"
    ALCOL = "alcol"
    GLUTINE = "glutine"
    LATTOSIO = "lattosio"
    FRUTTA_A_GUSCIO = "frutta_a_guscio"


class TipoEsclusione(StrEnum):
    ALLERGIA = "allergia"
    DIETA = "dieta"


class UnitaBase(StrEnum):
    KG = "kg"
    L = "L"
    PEZZO = "pezzo"


class UnitaDiVendita(StrEnum):
    PEZZO = "pezzo"
    PESO_VARIABILE = "peso_variabile"


class TipoDurata(StrEnum):
    SCADENZA_REALE = "scadenza_reale"
    DURATA_STIMATA = "durata_stimata"
    NON_DEPERIBILE = "non_deperibile"


class Fonte(StrEnum):
    """Origine di un dato estratto o dedotto (provenienza)."""

    VOLANTINO = "volantino"
    SCONTRINO = "scontrino"
    UMANO = "umano"
    REGOLA = "regola"


class StatoProvenienza(StrEnum):
    AUTO = "auto"
    RIVISTO = "rivisto"
    RIFIUTATO = "rifiutato"


class TipoVolantino(StrEnum):
    SETTIMANALE = "settimanale"
    CATALOGO = "catalogo"


class CondizioneOfferta(StrEnum):
    NESSUNA = "nessuna"
    CARTA_FEDELTA = "carta_fedelta"
    MULTI_ACQUISTO = "multi_acquisto"
