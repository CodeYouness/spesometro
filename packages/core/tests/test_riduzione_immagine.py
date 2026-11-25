"""Riduzione dell'immagine: seam pubblico `riduci_immagine` (byte in, byte JPEG + dimensioni out).

Le immagini sono generate al volo con Pillow: mai foto reali (ADR 0011).
"""

import io
import os

import pytest
from PIL import Image
from spesometro_core.riduzione_immagine import (
    LATO_MAX_PX,
    PESO_MAX_BYTE,
    ErroreImmagine,
    riduci_immagine,
)


def _codifica(immagine: Image.Image, formato: str = "JPEG", **opzioni: object) -> bytes:
    buffer = io.BytesIO()
    immagine.save(buffer, format=formato, **opzioni)
    return buffer.getvalue()


def _apri(dati: bytes) -> Image.Image:
    return Image.open(io.BytesIO(dati))


def test_immagine_grande_ridotta_entro_i_limiti_con_proporzioni_mantenute() -> None:
    originale = _codifica(Image.new("RGB", (4000, 3000), (200, 30, 30)))

    risultato = riduci_immagine(originale)

    assert (risultato.larghezza, risultato.altezza) == (LATO_MAX_PX, 1155)
    assert len(risultato.jpeg) <= PESO_MAX_BYTE
    immagine = _apri(risultato.jpeg)
    assert immagine.size == (risultato.larghezza, risultato.altezza)


def test_immagine_piccola_non_viene_ingrandita() -> None:
    risultato = riduci_immagine(_codifica(Image.new("RGB", (300, 200), (10, 10, 10))))

    assert (risultato.larghezza, risultato.altezza) == (300, 200)


def test_ingresso_webp_e_uscita_sempre_jpeg() -> None:
    originale = _codifica(Image.new("RGB", (800, 600), (0, 120, 0)), "WEBP")

    risultato = riduci_immagine(originale)

    assert _apri(risultato.jpeg).format == "JPEG"


def test_png_con_trasparenza_appiattito_su_bianco() -> None:
    originale = _codifica(Image.new("RGBA", (100, 100), (255, 0, 0, 0)), "PNG")

    risultato = riduci_immagine(originale)

    immagine = _apri(risultato.jpeg)
    assert immagine.mode == "RGB"
    r, g, b = immagine.getpixel((50, 50))
    assert min(r, g, b) >= 250


def test_modalita_non_compatibile_con_jpeg_convertita() -> None:
    originale = _codifica(Image.new("P", (50, 50), 3), "PNG")

    assert _apri(riduci_immagine(originale).jpeg).format == "JPEG"


def test_orientamento_exif_applicato() -> None:
    sorgente = Image.new("RGB", (400, 200), (255, 255, 255))
    exif = Image.Exif()
    exif[0x0112] = 6  # ruotata di 90 gradi in senso orario alla visualizzazione
    originale = _codifica(sorgente, exif=exif)

    risultato = riduci_immagine(originale)

    assert (risultato.larghezza, risultato.altezza) == (200, 400)
    assert _apri(risultato.jpeg).size == (200, 400)


def test_nessun_metadato_in_uscita_gps_compreso() -> None:
    exif = Image.Exif()
    exif[0x010F] = "MarcaTelefono"
    exif[0x0132] = "2026:11:26 10:00:00"
    exif.get_ifd(0x8825)[1] = "N"  # GPSLatitudeRef
    originale = _codifica(Image.new("RGB", (200, 200), (9, 9, 9)), exif=exif)
    assert len(_apri(originale).getexif()) > 0  # il sorgente li ha davvero

    uscita = _apri(riduci_immagine(originale).jpeg)

    assert len(uscita.getexif()) == 0
    assert b"Exif" not in riduci_immagine(originale).jpeg[:64]
    assert b"MarcaTelefono" not in riduci_immagine(originale).jpeg
    assert "exif" not in uscita.info


def test_immagine_rumorosa_costringe_a_ridurre_i_pixel_oltre_la_qualita_minima() -> None:
    rumore = Image.frombytes("RGB", (3000, 3000), os.urandom(3000 * 3000 * 3))
    originale = _codifica(rumore, "PNG")

    risultato = riduci_immagine(originale)

    assert len(risultato.jpeg) <= PESO_MAX_BYTE
    assert max(risultato.larghezza, risultato.altezza) < LATO_MAX_PX
    assert risultato.larghezza == risultato.altezza  # proporzioni mantenute
    assert _apri(risultato.jpeg).size == (risultato.larghezza, risultato.altezza)


def test_file_non_immagine_da_errore_di_dominio() -> None:
    with pytest.raises(ErroreImmagine, match="non è un'immagine"):
        riduci_immagine(b"questo non e' un file immagine")


def test_immagine_troncata_da_errore_di_dominio() -> None:
    rumore = Image.frombytes("RGB", (200, 200), os.urandom(200 * 200 * 3))
    intero = _codifica(rumore, "PNG")

    with pytest.raises(ErroreImmagine, match="corrotta o troncata"):
        riduci_immagine(intero[: len(intero) // 2])


def test_formato_non_ammesso_da_errore_di_dominio() -> None:
    gif = _codifica(Image.new("RGB", (20, 20)), "GIF")

    with pytest.raises(ErroreImmagine, match="formato non ammesso"):
        riduci_immagine(gif)


def test_numero_di_pixel_abnorme_da_errore_di_dominio() -> None:
    # PNG a un solo colore: pesa pochi KB ma dichiara molti più pixel del consentito.
    enorme = _codifica(Image.new("1", (20000, 20000)), "PNG")

    with pytest.raises(ErroreImmagine, match="troppi pixel"):
        riduci_immagine(enorme)
