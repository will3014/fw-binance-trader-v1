"""Public Spot universe discovery. No account credentials or order endpoints."""
import requests

BASE = 'https://api.binance.com'
FAVORITES = ['GRTUSDT','PEPEUSDT','BTCUSDT','ETHUSDT','XRPUSDT','SOLUSDT','ADAUSDT','DOGEUSDT']


def discover_spot_usdt(timeout=15):
    response = requests.get(f'{BASE}/api/v3/exchangeInfo', timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get('symbols'), list):
        raise ValueError('Catálogo Binance inválido')
    return sorted(s['symbol'] for s in data['symbols'] if
        s.get('status') == 'TRADING' and s.get('quoteAsset') == 'USDT'
        and s.get('isSpotTradingAllowed') is True
        and 'SPOT' in s.get('permissions', ['SPOT']))


def top_liquid_pairs(eligible, limit=30, min_quote_volume=1_000_000, timeout=15):
    response = requests.get(f'{BASE}/api/v3/ticker/24hr', timeout=timeout)
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError('Volume Binance inválido')
    allowed = set(eligible)
    ranked = []
    for row in rows:
        symbol = row.get('symbol')
        if symbol not in allowed:
            continue
        try:
            volume = float(row.get('quoteVolume', 0))
        except (TypeError, ValueError):
            continue
        if volume >= min_quote_volume:
            ranked.append((symbol, volume))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in ranked[:limit]]
