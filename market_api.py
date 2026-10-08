
"""FW BINANCE TRADER V1 — API pública de mercado.

Duas fontes oficiais, fallback automático e proteção
contra excesso de requisições. Somente leitura.
"""

import time
import threading
import requests

ENDPOINTS = (
    "https://api.binance.com",
    "https://data-api.binance.vision",
)

ALLOWED_PATHS = {
    "/api/v3/exchangeInfo",
    "/api/v3/ticker/24hr",
    "/api/v3/klines",
}

_session = requests.Session()
_lock = threading.RLock()

_preferred = 0
_cooldown_until = [0.0] * len(ENDPOINTS)
_last_errors = {}

COOLDOWN_SECONDS = 60
RESTRICTED_COOLDOWN_SECONDS = 3600


class MarketAPIError(RuntimeError):
    """Falha ao obter dados públicos de mercado."""


def api_status():
    """Retorna o estado atual dos endpoints."""
    with _lock:
        now = time.monotonic()

        return {
            endpoint: {
                "available_for_retry": now >= _cooldown_until[i],
                "retry_after_seconds": max(
                    0, round(_cooldown_until[i] - now)
                ),
                "last_error": _last_errors.get(endpoint),
            }
            for i, endpoint in enumerate(ENDPOINTS)
        }


def public_get(path, params=None, timeout=12):
    """Consulta dados públicos sem autenticação ou ordens."""
    global _preferred

    if path not in ALLOWED_PATHS:
        raise ValueError(
            "Endpoint público não autorizado"
        )

    if params is not None and not isinstance(params, dict):
        raise ValueError("Parâmetros inválidos")

    with _lock:
        order = [
            _preferred,
            *(
                i for i in range(len(ENDPOINTS))
                if i != _preferred
            ),
        ]

    errors = []

    for index in order:
        endpoint = ENDPOINTS[index]

        with _lock:
            remaining = (
                _cooldown_until[index] - time.monotonic()
            )

        if remaining > 0:
            errors.append(
                f"{endpoint}: aguardando "
                f"{remaining:.0f}s"
            )
            continue

        try:
            response = _session.get(
                endpoint + path,
                params=params,
                timeout=timeout,
            )

            response.raise_for_status()
            data = response.json()

            if not isinstance(data, (dict, list)):
                raise ValueError(
                    "Formato JSON inesperado"
                )

            with _lock:
                _preferred = index
                _cooldown_until[index] = 0.0
                _last_errors.pop(endpoint, None)

            return data

        except requests.HTTPError as exc:
            status = (
                exc.response.status_code
                if exc.response is not None
                else None
            )

            if status == 451:
                delay = RESTRICTED_COOLDOWN_SECONDS
                reason = "HTTP 451: acesso restrito"

            elif status == 429:
                delay = COOLDOWN_SECONDS
                reason = "HTTP 429: limite de requisições"

            elif status == 418:
                delay = RESTRICTED_COOLDOWN_SECONDS
                reason = "HTTP 418: bloqueio temporário"

            else:
                delay = COOLDOWN_SECONDS
                reason = f"HTTP {status}"

            with _lock:
                _cooldown_until[index] = (
                    time.monotonic() + delay
                )
                _last_errors[endpoint] = reason

            errors.append(f"{endpoint}: {reason}")

        except (
            requests.RequestException,
            ValueError,
        ) as exc:
            reason = (
                f"{type(exc).__name__}: {exc}"
            )

            with _lock:
                _cooldown_until[index] = (
                    time.monotonic() + COOLDOWN_SECONDS
                )
                _last_errors[endpoint] = reason

            errors.append(f"{endpoint}: {reason}")

    raise MarketAPIError(
        "Nenhuma API Binance disponível. "
        + " | ".join(errors)
    )
