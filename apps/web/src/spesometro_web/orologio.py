"""Orologio iniettabile: istanti con fuso UTC."""

from collections.abc import Callable
from datetime import UTC, datetime

type Orologio = Callable[[], datetime]


def orologio_utc() -> datetime:
    return datetime.now(UTC)
