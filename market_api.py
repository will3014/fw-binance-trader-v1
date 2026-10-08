
"""Binance: consultas públicas com duas APIs e fallback automático."""
import time
import requests

ENDPOINTS = (
    "https://api.binance.com",
    "https://data-api.binance.vision",
)

_session = requests.Session()
_preferred = 0
_cooldown_until = [0.0, 0.0]


def public_get(path, params=None, timeout=12):
    """Consulta apenas dados públicos; nunca envia ordens."""
    global _preferred

    allowed = (
        "/api/v3/exchangeInfo",
        "/api/v3/ticker/24hr",
        "/api/v3/klines",
    )
    if path not in allowed:
        raise ValueError("Endpoint público não autorizado")

    last_error = None

    for index in (_preferred, 1 - _preferred):
        if time.monotonic() < _cooldown_until[index]:
            continue

        try:
            response = _session.get(
                ENDPOINTS[index] + path,
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            if not isinstance(data, (dict, list)):
                raise ValueError("Resposta JSON inválida")

            _preferred = index
            return data

        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            _cooldown_until[index] = time.monotonic() + 60

    raise RuntimeError(
        f"Nenhuma API pública disponível: {last_error}"
    )
