"""Provider registry."""
from __future__ import annotations

from .base import Provider, make_session
from .chronogolf import ChronogolfProvider
from .foreup import ForeUpProvider
from .nassau import NassauProvider
from .teeitup import TeeItUpProvider

_REGISTRY = {
    "foreup": ForeUpProvider,
    "teeitup": TeeItUpProvider,
    "chronogolf": ChronogolfProvider,
    "nassau": NassauProvider,
}


def get_provider(name: str, session=None, debug: bool = False) -> Provider:
    if name not in _REGISTRY:
        raise KeyError(f"No provider '{name}'. Known: {', '.join(_REGISTRY)}")
    return _REGISTRY[name](session=session, debug=debug)
