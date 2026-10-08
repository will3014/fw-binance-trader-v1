
"""
FW BINANCE TRADER V1
Radar Binance Spot + Paper Trading + FW CRYPTO AI

Capital inicial: R$ 1.000
Mercado: Spot / USDT
Estratégias: Swing Trade e Day Trade
Execução real: DESATIVADA
"""

import streamlit as st
import pandas as pd

from decimal import Decimal
from datetime import datetime, timezone

from engine import candles, signal, PaperAccount
from universe import (
    discover_spot_usdt,
    top_liquid_pairs,
    FAVORITES,
)
from portfolio import ASSETS, PortfolioPolicy
from crypto_ai import responder


# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================

st.set_page_config(
    page_title="FW Binance Trader V1",
    page_icon="📊",
    layout="wide",
)

st.title("FW BINANCE TRADER V1")

st.warning(
    "MODO SIMULAÇÃO — nenhuma ordem real é enviada. "
    "O câmbio BRL/USDT é informado manualmente."
)


# ==========================================
# ESTADO DA APLICAÇÃO
# ==========================================

def initialize_state():
    if "account" not in st.session_state:
        st.session_state.account = PaperAccount(
            initial_brl=1000.0,
            brl_per_usdt=5.0,
        )

    if "policy" not in st.session_state:
        st.session_state.policy = PortfolioPolicy()

    defaults = {
        "processed": set(),
        "market_frames": {},
        "last_results": [],
        "last_marks": {},
        "crypto_chat": [],
        "last_update": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_state()


# ==========================================
# CAPITAL E CÂMBIO
# ==========================================

fx = st.number_input(
    "BRL por 1 USDT (cotação de referência)",
    min_value=0.01,
    value=5.0,
    step=0.05,
    format="%.2f",
)

account = st.session_state.account

if abs(fx - account.brl_per_usdt) > 0.000001:
    st.info(
        "O câmbio da simulação está fixado. "
        "Reinicie para aplicar o novo valor."
    )

if st.button("🔄 Reiniciar simulação"):
    st.session_state.account = PaperAccount(
        initial_brl=1000.0,
        brl_per_usdt=fx,
    )

    st.session_state.processed = set()
    st.session_state.market_frames = {}
    st.session_state.last_results = []
    st.session_state.last_marks = {}
    st.session_state.crypto_chat = []
    st.session_state.last_update = None

    st.rerun()


# ==========================================
# CONSULTAS BINANCE
# ==========================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_universe():
    return discover_spot_usdt()


@st.cache_data(ttl=300, show_spinner=False)
def get_liquid(universe, limit, minimum):
    return top_liquid_pairs(
        universe,
        limit=limit,
        min_quote_volume=minimum,
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_candles(symbol, interval):
    return candles(
        symbol,
        interval,
    )


try:
    universe = list(get_universe())

    if not universe:
        raise ValueError("Catálogo vazio")

    catalog_ok = True

except Exception as exc:
    st.warning(
        "Não foi possível atualizar o catálogo Binance. "
        "Usando favoritos como alternativa."
    )

    st.caption(str(exc))

    universe = list(FAVORITES)
    catalog_ok = False

universe = sorted(set(universe))

st.caption(
    f"Pares disponíveis no catálogo: {len(universe)} "
    f"| Catálogo atualizado: {'Sim' if catalog_ok else 'Não'}"
)


# ==========================================
# CONFIGURAÇÃO DO RADAR
# ==========================================

st.subheader("📡 Radar Binance Spot")

mode = st.radio(
    "Modo do radar",
    [
        "Favoritos",
        "Mais líquidos",
        "Seleção manual",
    ],
    horizontal=True,
)

if mode == "Favoritos":
    defaults = [
        symbol
        for symbol in FAVORITES
        if symbol in universe
    ]

elif mode == "Mais líquidos":
    scan_limit = st.slider(
        "Máximo de pares por atualização",
        min_value=5,
        max_value=50,
        value=20,
        step=5,
    )

    min_volume = st.number_input(
        "Volume mínimo 24h (USDT)",
        min_value=0.0,
        value=1_000_000.0,
        step=500_000.0,
    )

    try:
        defaults = get_liquid(
            tuple(universe),
            scan_limit,
            min_volume,
        )

        defaults = [
            symbol
            for symbol in defaults
            if symbol in universe
        ]

    except Exception as exc:
        st.warning(
            f"Falha na consulta de liquidez: {exc}"
        )

        defaults = [
            symbol
            for symbol in FAVORITES
            if symbol in universe
        ]

else:
    defaults = []

selected = st.multiselect(
    "Criptomoedas para monitoramento",
    options=universe,
    default=defaults[:50],
    max_selections=50,
)

st.caption(
    "Mercado Spot/USDT. Até 50 pares por atualização. "
    "A coleta ocorre quando você solicita."
)


# ==========================================
# PROTEÇÃO FUTURA DA CARTEIRA
# ==========================================

st.sidebar.header("🛡️ Proteção da carteira")

st.sidebar.info(
    "Configuração preventiva. "
    "Não acessa saldos reais da Binance."
)

policy = st.session_state.policy

# CORREÇÃO DO ERRO TYPEERROR
# Funciona com ASSETS como lista, tupla ou set.

assets = sorted(
    set(ASSETS).union(
        symbol.removesuffix("USDT")
        for symbol in selected
    )
)

for asset in assets:
    current = float(
        policy.protected_minimum.get(
            asset,
            0,
        )
    )

    minimum = st.sidebar.number_input(
        f"{asset} — saldo mínimo protegido",
        min_value=0.0,
        value=current,
        format="%.8f",
        key=f"protected_{asset}",
    )

    policy.protected_minimum[asset] = Decimal(
        str(minimum)
    )

st.sidebar.error(
    "🔒 EXECUÇÃO REAL DESATIVADA"
)


# ==========================================
# EXECUÇÃO DA SIMULAÇÃO
# ==========================================

st.subheader("⚙️ Motor de simulação")

run = st.button(
    "▶️ Atualizar radar e simular",
    type="primary",
)

if run:
    if not selected:
        st.warning(
            "Selecione pelo menos uma criptomoeda."
        )

    else:
        marks = dict(
            st.session_state.last_marks
        )

        data = {}
        results = []
        errors = []

        progress = st.progress(0)

        total = len(selected) * 2
        completed = 0

        with st.spinner(
            "Consultando candles fechados..."
        ):
            for symbol in selected:
                for strategy, interval in [
                    ("swing", "4h"),
                    ("day", "15m"),
                ]:
                    try:
                        df = get_candles(
                            symbol,
                            interval,
                        )

                        if df is None or df.empty:
                            raise ValueError(
                                "Sem candles disponíveis"
                            )

                        data[(symbol, strategy)] = df

                        marks[symbol] = float(
                            df["close"].iloc[-1]
                        )

                    except Exception as exc:
                        errors.append(
                            f"{symbol} {interval}: {exc}"
                        )

                    finally:
                        completed += 1

                        progress.progress(
                            min(
                                completed / total,
                                1.0,
                            )
                        )

        account.roll_day(marks)

        for (symbol, strategy), df in data.items():
            try:
                result = signal(
                    df,
                    strategy,
                )

                candle_time = result.get(
                    "candle_time"
                )

                candle_id = (
                    symbol,
                    strategy,
                    candle_time,
                )

                if candle_time is None:
                    errors.append(
                        f"{symbol} {strategy}: "
                        "candle sem identificação."
                    )

                elif candle_id not in st.session_state.processed:

                    # Verifica saídas somente da
                    # estratégia correspondente.

                    if (
                        symbol,
                        strategy,
                    ) in account.positions:

                        events = account.check_exits(
                            symbol,
                            float(df["low"].iloc[-1]),
                            float(df["high"].iloc[-1]),
                            marks,
                            strategy=strategy,
                        )

                        for event in events:
                            st.info(event)

                    # Compra exclusivamente simulada.

                    if result.get("action") == "BUY":
                        message = account.buy(
                            symbol,
                            strategy,
                            result["price"],
                            marks,
                        )

                        st.info(message)

                    st.session_state.processed.add(
                        candle_id
                    )

                results.append({
                    "Par": symbol,
                    "Estratégia": strategy.upper(),
                    "Sinal": result.get(
                        "action",
                        "WAIT",
                    ),
                    "Preço USDT": result.get(
                        "price"
                    ),
                    "RSI": result.get("rsi"),
                    "Motivo": result.get("reason"),
                    "Candle fechado": candle_time,
                })

            except Exception as exc:
                errors.append(
                    f"{symbol} {strategy}: {exc}"
                )

        st.session_state.last_results = results
        st.session_state.last_marks = marks
        st.session_state.market_frames = data

        st.session_state.last_update = (
            datetime.now(timezone.utc).isoformat()
        )

        if errors:
            with st.expander(
                f"Falhas na atualização ({len(errors)})"
            ):
                for error in errors:
                    st.warning(error)

        if results:
            st.success(
                f"Radar atualizado: "
                f"{len(results)} análises realizadas."
            )
        else:
            st.warning(
                "Nenhuma análise concluída. "
                "Verifique a conexão com a Binance."
            )


# ==========================================
# PAINEL GERENCIAL
# ==========================================

st.divider()
st.subheader("📊 Painel gerencial")

marks = st.session_state.last_marks

col1, col2, col3 = st.columns(3)

col1.metric(
    "Caixa disponível (USDT)",
    f"{account.cash_usdt:.2f}",
)

col2.metric(
    "Patrimônio simulado (USDT)",
    f"{account.equity(marks):.2f}",
)

col3.metric(
    "Posições abertas",
    len(account.positions),
)

st.caption(
    "Patrimônio calculado com as últimas "
    "cotações disponíveis na sessão."
)

if st.session_state.last_update:
    st.caption(
        "Última atualização UTC: "
        f"{st.session_state.last_update}"
    )


# ==========================================
# RESULTADOS DO RADAR
# ==========================================

st.subheader("📈 Sinais do radar")

results_df = pd.DataFrame(
    st.session_state.last_results
)

if not results_df.empty:
    st.dataframe(
        results_df,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.info(
        "Atualize o radar para visualizar sinais."
    )


# ==========================================
# POSIÇÕES SIMULADAS
# ==========================================

st.subheader("💼 Posições simuladas")

positions_df = pd.DataFrame([
    vars(position)
    for position in account.positions.values()
])

if not positions_df.empty:
    st.dataframe(
        positions_df,
        use_container_width=True,
        hide_index=True,
    )

else:
    st.info(
        "Nenhuma posição simulada aberta."
    )


# ==========================================
# HISTÓRICO DE OPERAÇÕES
# ==========================================

st.subheader("📋 Operações encerradas")

trades_df = pd.DataFrame(
    account.trades
)

if not trades_df.empty:
    st.dataframe(
        trades_df,
        use_container_width=True,
        hide_index=True,
    )

    if "pnl_usdt" in trades_df.columns:
        total_pnl = trades_df[
            "pnl_usdt"
        ].sum()

        st.metric(
            "Resultado realizado (USDT)",
            f"{total_pnl:+.4f}",
        )

else:
    st.info(
        "Nenhuma operação simulada encerrada."
    )


# ==========================================
# FW CRYPTO AI — CHAT
# ==========================================

st.divider()

st.subheader("🤖 FW CRYPTO AI")

st.info(
    "Assistente gratuito baseado em regras. "
    "Analisa candles do radar e explica "
    "indicadores. Não envia ordens."
)

strategy_ai = st.radio(
    "Estratégia para análise da IA",
    options=["swing", "day"],
    horizontal=True,
    format_func=lambda value: (
        "Swing Trade — 4h"
        if value == "swing"
        else "Day Trade — 15min"
    ),
)

frames = st.session_state.market_frames

chat_data = {
    symbol: df
    for (symbol, strategy), df
    in frames.items()
    if strategy == strategy_ai
}

if not chat_data:
    st.warning(
        "Atualize o radar antes de solicitar "
        "análises técnicas ao assistente."
    )

st.caption(
    "Exemplos: Analise GRT, "
    "Qual o suporte do BTC?, "
    "Explique Swing Trade, "
    "Qual meu limite de risco?"
)

for message in st.session_state.crypto_chat:
    with st.chat_message(
        message["role"]
    ):
        st.markdown(
            message["content"]
        )

question = st.chat_input(
    "Converse com o FW CRYPTO AI..."
)

if question:
    st.session_state.crypto_chat.append({
        "role": "user",
        "content": question,
    })

    try:
        answer = responder(
            question,
            dados=chat_data,
            estrategia=strategy_ai,
        )

    except Exception as exc:
        answer = (
            "Não foi possível concluir a análise. "
            f"Detalhes: {exc}"
        )

    st.session_state.crypto_chat.append({
        "role": "assistant",
        "content": answer,
    })

    st.rerun()


if st.button("🗑️ Limpar conversa"):
    st.session_state.crypto_chat = []
    st.rerun()


# ==========================================
# INFORMAÇÕES DE SEGURANÇA
# ==========================================

st.divider()

st.caption(
    "FW BINANCE TRADER V1 — Ambiente de testes. "
    "Sem execução real, sem alavancagem, "
    "sem leitura de saldos privados. "
    "Não funciona continuamente em segundo plano."
)

st.caption(
    "Os sinais são experimentais. "
    "O simulador ainda não realiza backtest "
    "cronológico completo nem garante "
    "preços de execução, taxas ou liquidez."
)
