"""Riduzione dell'immagine: byte di una foto in ingresso, JPEG entro i limiti in uscita (ADR 0007).

Sempre ricodificata (anche se già nei limiti): prima l'orientamento EXIF, poi nessun metadato
viene riportato in uscita. Nessun legame con upload o provider (lo fa il ticket 08).
"""

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

LATO_MAX_PX = 1540
PESO_MAX_BYTE = 400 * 1024
QUALITA_INIZIALE = 85
QUALITA_MINIMA = 60
PASSO_QUALITA = 5
PASSO_RIDUZIONE = 0.85
PIXEL_MAX = 50_000_000
FORMATI_AMMESSI = frozenset({"JPEG", "PNG", "WEBP"})
_MESSAGGIO_TROPPI_PIXEL = f"immagine con troppi pixel (massimo {PIXEL_MAX})"


class ErroreImmagine(ValueError):
    """File non utilizzabile come immagine: il messaggio dice quale dei casi."""


@dataclass(frozen=True)
class ImmagineRidotta:
    jpeg: bytes
    larghezza: int
    altezza: int


def riduci_immagine(dati: bytes) -> ImmagineRidotta:
    immagine = _carica(dati)
    immagine = ImageOps.exif_transpose(immagine)
    immagine = _in_rgb_su_bianco(immagine)
    immagine.thumbnail((LATO_MAX_PX, LATO_MAX_PX))  # mai ingrandisce

    while True:
        for qualita in range(QUALITA_INIZIALE, QUALITA_MINIMA - 1, -PASSO_QUALITA):
            jpeg = _codifica(immagine, qualita)
            if len(jpeg) <= PESO_MAX_BYTE:
                return ImmagineRidotta(jpeg, *immagine.size)
        larghezza = max(1, int(immagine.width * PASSO_RIDUZIONE))
        altezza = max(1, int(immagine.height * PASSO_RIDUZIONE))
        immagine = immagine.resize((larghezza, altezza), Image.Resampling.LANCZOS)


def _carica(dati: bytes) -> Image.Image:
    # Pillow, di default, non tollera i file troncati: li segnala con OSError al caricamento.
    # Il limite è `PIXEL_MAX`, non quello di Pillow: il suo DecompressionBombWarning (sopra
    # ~89 Mpx) non deve uscire; oltre ~178 Mpx Pillow solleva un errore, stesso messaggio.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            immagine = Image.open(io.BytesIO(dati))
    except (UnidentifiedImageError, OSError) as errore:
        raise ErroreImmagine("il file non è un'immagine riconoscibile") from errore
    except Image.DecompressionBombError as errore:
        raise ErroreImmagine(_MESSAGGIO_TROPPI_PIXEL) from errore
    if immagine.format not in FORMATI_AMMESSI:
        raise ErroreImmagine(f"formato non ammesso: {immagine.format} (solo JPEG, PNG, WebP)")
    if immagine.width * immagine.height > PIXEL_MAX:
        raise ErroreImmagine(_MESSAGGIO_TROPPI_PIXEL)
    try:
        immagine.load()
    except Image.DecompressionBombError as errore:
        raise ErroreImmagine(_MESSAGGIO_TROPPI_PIXEL) from errore
    except (OSError, SyntaxError, ValueError) as errore:
        raise ErroreImmagine("immagine corrotta o troncata") from errore
    return immagine


def _codifica(immagine: Image.Image, qualita: int) -> bytes:
    buffer = io.BytesIO()
    immagine.save(buffer, format="JPEG", quality=qualita)
    return buffer.getvalue()


def _in_rgb_su_bianco(immagine: Image.Image) -> Image.Image:
    """Appiattisce le trasparenze su bianco e porta ogni modalità a RGB (compatibile con JPEG)."""
    if immagine.mode == "P" and "transparency" in immagine.info:
        immagine = immagine.convert("RGBA")
    if immagine.mode in ("RGBA", "LA"):
        immagine = immagine.convert("RGBA")
        fondo = Image.new("RGB", immagine.size, (255, 255, 255))
        fondo.paste(immagine, mask=immagine.getchannel("A"))
        return fondo
    return immagine.convert("RGB")
