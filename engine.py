
"""FW Binance Trader V1 — Simulação Spot, sem ordens reais."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math

import pandas as pd
from market_api import public_get


SYMBOLS = [
    "GRTUSDT", "PEPEUSDT", "BTCUSDT", "ETHUSDT",
    "XRPUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT",
]


def candles(symbol: str, interval: str, limit: int = 250):
    """Consulta candles fechados da Binance."""

    if (
        not isinstance(symbol, str)
        or not symbol.endswith("USDT")
        or not symbol[:-4].isalnum()
        or interval not in ("15m", "4h")
        or not isinstance(limit, int)
        or not 60 <= limit <= 1000
    ):
        raise ValueError("Par, intervalo ou limite inválido")

    rows = public_get(
        "/api/v3/klines",
        params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        },
        timeout=12,
    )

    if not isinstance(rows, list) or not rows:
        raise ValueError("Resposta de mercado inválida")

    columns = [
        "open_time", "open", "high", "low", "close",
        "volume", "close_time", "qav", "trades",
        "taker_base", "taker_quote", "ignore",
    ]

    df = pd.DataFrame(rows, columns=columns)

    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="raise")

    df["close_time"] = pd.to_datetime(
        df["close_time"], unit="ms", utc=True
    )

    df = df[
        df["close_time"] <= pd.Timestamp.now(tz="UTC")
    ].copy()

    if df.empty:
        raise ValueError("Nenhum candle fechado disponível")

    return df.reset_index(drop=True)


def signal(df: pd.DataFrame, strategy: str):
    """Identifica sinal técnico de compra."""

    if strategy not in ("swing", "day"):
        raise ValueError("Estratégia inválida")

    if len(df) < 60:
        return {
            "action": "WAIT",
            "reason": "Histórico insuficiente",
        }

    close = df["close"]

    fast_span, slow_span = (
        (21, 50) if strategy == "swing" else (9, 21)
    )

    fast = close.ewm(
        span=fast_span, adjust=False
    ).mean()

    slow = close.ewm(
        span=slow_span, adjust=False
    ).mean()

    delta = close.diff()

    up = delta.clip(lower=0).ewm(
        alpha=1 / 14, adjust=False
    ).mean()

    down = (-delta.clip(upper=0)).ewm(
        alpha=1 / 14, adjust=False
    ).mean()

    last = len(df) - 1
    prev = last - 1

    gain = float(up.iloc[last])
    loss = float(down.iloc[last])

    if loss == 0:
        rsi = 100.0 if gain > 0 else 50.0
    else:
        rsi = 100 - 100 / (1 + gain / loss)

    crossed = (
        fast.iloc[prev] <= slow.iloc[prev]
        and fast.iloc[last] > slow.iloc[last]
    )

    trend = close.iloc[last] > slow.iloc[last]
    momentum = 45 <= rsi <= 70

    action = (
        "BUY" if crossed and trend and momentum
        else "WAIT"
    )

    return {
        "action": action,
        "price": float(close.iloc[last]),
        "rsi": rsi,
        "fast": float(fast.iloc[last]),
        "slow": float(slow.iloc[last]),
        "reason": (
            "Cruzamento confirmado e RSI adequado"
            if action == "BUY"
            else "Sem confirmação de entrada"
        ),
        "candle_time": df["close_time"].iloc[last].isoformat(),
    }


@dataclass
class Position:
    symbol: str
    strategy: str
    quantity: float
    entry: float
    stop: float
    target: float
    fee_paid: float


@dataclass
class PaperAccount:
    initial_brl: float = 1000.0
    brl_per_usdt: float = 5.0

    cash_usdt: float = field(init=False)
    positions: dict = field(default_factory=dict)
    trades: list = field(default_factory=list)

    day_start_equity: float = field(init=False)

    day: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).date().isoformat()
    )

    fee_rate: float = 0.001
    max_positions: int = 3
    max_daily_loss_pct: float = 0.02
    risk_per_trade_pct: float = 0.005
    slippage_rate: float = 0.0005

    def __post_init__(self):
        if (
            not math.isfinite(self.brl_per_usdt)
            or self.brl_per_usdt <= 0
            or not math.isfinite(self.initial_brl)
            or self.initial_brl <= 0
        ):
            raise ValueError("Capital ou câmbio inválido")

        self.cash_usdt = (
            self.initial_brl / self.brl_per_usdt
        )

        self.day_start_equity = self.cash_usdt

    def equity(self, marks: dict):
        """Patrimônio simulado marcado a mercado."""

        return self.cash_usdt + sum(
            p.quantity * marks.get(p.symbol, p.entry)
            for p in self.positions.values()
        )

    def roll_day(self, marks: dict):
        """Atualiza referência de perda diária em UTC."""

        today = datetime.now(
            timezone.utc
        ).date().isoformat()

        if today != self.day:
            self.day = today
            self.day_start_equity = self.equity(marks)

    def buy(
        self,
        symbol: str,
        strategy: str,
        market_price: float,
        marks: dict,
    ):
        """Abre exclusivamente uma posição simulada."""

        self.roll_day(marks)

        if strategy not in ("swing", "day"):
            return "Bloqueado: estratégia inválida"

        key = (symbol, strategy)

        if (
            key in self.positions
            or len(self.positions) >= self.max_positions
        ):
            return (
                "Bloqueado: posição existente "
                "ou limite de 3 posições"
            )

        if self.equity(marks) <= (
            self.day_start_equity
            * (1 - self.max_daily_loss_pct)
        ):
            return "Bloqueado: limite de perda diária"

        if (
            not math.isfinite(market_price)
            or market_price <= 0
        ):
            return "Bloqueado: preço inválido"

        entry = market_price * (
            1 + self.slippage_rate
        )

        stop = entry * 0.98
        target = entry * 1.04

        risk_budget = (
            self.equity(marks)
            * self.risk_per_trade_pct
        )

        risk_per_unit = (
            (entry - stop)
            + entry * self.fee_rate
            + stop * self.fee_rate
        )

        if risk_per_unit <= 0:
            return "Bloqueado: risco inválido"

        qty = min(
            risk_budget / risk_per_unit,
            self.cash_usdt
            / (entry * (1 + self.fee_rate)),
        )

        if qty <= 0 or not math.isfinite(qty):
            return "Bloqueado: saldo insuficiente"

        # Limite mínimo aproximado para simulação.
        # Não substitui filtros oficiais da Binance.
        if qty * entry < 10:
            return (
                "Bloqueado: posição inferior "
                "a 10 USDT"
            )

        fee = qty * entry * self.fee_rate
        cost = qty * entry + fee

        if cost > self.cash_usdt:
            return "Bloqueado: saldo insuficiente"

        self.cash_usdt -= cost

        self.positions[key] = Position(
            symbol=symbol,
            strategy=strategy,
            quantity=qty,
            entry=entry,
            stop=stop,
            target=target,
            fee_paid=fee,
        )

        return (
            f"COMPRA SIMULADA: {qty:.8f} "
            f"{symbol} a {entry:.8f} USDT "
            f"| Stop: {stop:.8f} "
            f"| Alvo: {target:.8f}"
        )

    def check_exits(
        self,
        symbol: str,
        low: float,
        high: float,
        marks: dict,
        strategy=None,
    ):
        """
        Verifica stops e alvos simulados.

        Quando strategy é informada, avalia
        somente posições daquela estratégia.
        """

        events = []

        if strategy not in (None, "swing", "day"):
            raise ValueError("Estratégia inválida")

        if (
            not math.isfinite(low)
            or not math.isfinite(high)
            or low <= 0
            or high < low
        ):
            raise ValueError("Máxima ou mínima inválida")

        for key, p in list(self.positions.items()):

            if p.symbol != symbol:
                continue

            # CORREÇÃO PRINCIPAL:
            # Não mistura Swing e Day Trade.
            if (
                strategy is not None
                and p.strategy != strategy
            ):
                continue

            # Critério conservador:
            # se ambos ocorrerem no candle,
            # o stop tem prioridade.
            if low <= p.stop:
                exit_price = p.stop * (
                    1 - self.slippage_rate
                )
                reason = "STOP"

            elif high >= p.target:
                exit_price = p.target * (
                    1 - self.slippage_rate
                )
                reason = "TARGET"

            else:
                continue

            proceeds = (
                p.quantity
                * exit_price
                * (1 - self.fee_rate)
            )

            pnl = (
                proceeds
                - p.quantity * p.entry
                - p.fee_paid
            )

            self.cash_usdt += proceeds

            self.trades.append({
                "time": datetime.now(
                    timezone.utc
                ).isoformat(),
                "symbol": symbol,
                "strategy": p.strategy,
                "entry": p.entry,
                "exit": exit_price,
                "quantity": p.quantity,
                "reason": reason,
                "pnl_usdt": pnl,
                "pnl_brl": pnl * self.brl_per_usdt,
            })

            del self.positions[key]

            events.append(
                f"SAÍDA SIMULADA {symbol} "
                f"({p.strategy}) | {reason} "
                f"| Resultado: {pnl:+.4f} USDT"
            )

        return events
