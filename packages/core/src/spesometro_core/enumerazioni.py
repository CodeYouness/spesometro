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
