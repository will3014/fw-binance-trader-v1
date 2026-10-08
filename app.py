
import streamlit as st
import pandas as pd
from decimal import Decimal

from engine import candles, signal, PaperAccount
from universe import discover_spot_usdt, top_liquid_pairs, FAVORITES
from portfolio import ASSETS, PortfolioPolicy
from crypto_ai import responder

st.set_page_config(
    page_title="FW Binance Trader V1",
    layout="wide"
)

st.title("FW BINANCE TRADER V1")
st.warning(
    "PAPER TRADING — nenhuma ordem real é enviada. "
    "O câmbio é manual, não uma cotação ao vivo."
)

fx = st.number_input(
    "BRL por 1 USDT (cotação de referência)",
    min_value=0.01,
    value=5.0,
    step=0.05
)

# ==========================================
# ESTADO DA SIMULAÇÃO
# ==========================================

if "account" not in st.session_state:
    st.session_state.account = PaperAccount(
        brl_per_usdt=fx
    )

if "policy" not in st.session_state:
    st.session_state.policy = PortfolioPolicy()

if "processed" not in st.session_state:
    st.session_state.processed = set()

if "market_frames" not in st.session_state:
    st.session_state.market_frames = {}

if "crypto_chat" not in st.session_state:
    st.session_state.crypto_chat = []

if st.button("Reiniciar simulação"):
    st.session_state.account = PaperAccount(
        brl_per_usdt=fx
    )

    for key in (
        "processed",
        "last_results",
        "last_marks",
        "market_frames"
    ):
        st.session_state.pop(key, None)

    st.rerun()

account = st.session_state.account

if abs(fx - account.brl_per_usdt) > 0.000001:
    st.info(
        "O câmbio da conta está fixado nesta sessão. "
        "Reinicie a simulação para alterá-lo."
    )

# ==========================================
# BINANCE — CACHE E CATÁLOGO
# ==========================================

@st.cache_data(ttl=3600)
def get_universe():
    return discover_spot_usdt()


@st.cache_data(ttl=300)
def get_liquid(universe, n, minimum):
    return top_liquid_pairs(
        universe,
        limit=n,
        min_quote_volume=minimum
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_candles(symbol, interval):
    return candles(symbol, interval)


try:
    universe = get_universe()
    catalog_ok = True

except Exception as exc:
    st.error(
        f"Catálogo Binance indisponível: {exc}. "
        "Usando favoritos como alternativa."
    )

    universe = FAVORITES
    catalog_ok = False

st.caption(
    f"{len(universe)} pares listados. "
    f"Catálogo atualizado: {catalog_ok}. "
    "Máximo de 50 pares por atualização."
)

# ==========================================
# RADAR DE CRIPTOMOEDAS
# ==========================================

mode = st.radio(
    "Modo do radar",
    [
        "Favoritos",
        "Mais líquidos",
        "Seleção manual"
    ],
    horizontal=True
)

if mode == "Favoritos":
    defaults = [
        s for s in FAVORITES
        if s in universe
    ]

elif mode == "Mais líquidos":
    scan_limit = st.slider(
        "Máximo de pares por atualização",
        5, 50, 20, 5
    )

    min_volume = st.number_input(
        "Volume mínimo 24h (USDT)",
        min_value=0.0,
        value=1_000_000.0,
        step=500_000.0
    )

    try:
        defaults = get_liquid(
            tuple(universe),
            scan_limit,
            min_volume
        )

    except Exception as exc:
        st.warning(
            f"Falha ao consultar volumes: {exc}"
        )

        defaults = [
            s for s in FAVORITES
            if s in universe
        ]

else:
    defaults = []

selected = st.multiselect(
    "Pares a analisar",
    universe,
    default=defaults,
    max_selections=50
)

st.caption(
    "Todos os pares Spot/USDT elegíveis podem "
    "ser selecionados. A análise é limitada "
    "para evitar excesso de requisições."
)

# ==========================================
# PROTEÇÃO FUTURA DA CARTEIRA
# ==========================================

st.sidebar.header(
    "Proteção futura da carteira"
)

st.sidebar.info(
    "Somente planejamento. "
    "Sem acesso a saldos reais ou envio de ordens."
)

policy = st.session_state.policy

assets = sorted(
    set(
        ASSETS + [
            symbol[:-4]
            for symbol in selected
        ]
    )
)

for asset in assets:
    current = float(
        policy.protected_minimum.get(
            asset, 0
        )
    )

    minimum = st.sidebar.number_input(
        f"{asset}: saldo mínimo protegido",
        min_value=0.0,
        value=current,
        format="%.8f",
        key=f"protected_{asset}"
    )

    policy.protected_minimum[asset] = Decimal(
        str(minimum)
    )

st.sidebar.error(
    "EXECUÇÃO REAL BLOQUEADA"
)

# ==========================================
# SIMULAÇÃO DE OPERAÇÕES
# ==========================================

run = st.button(
    "Atualizar radar e simular candles fechados"
)

if run:
    marks = dict(
        st.session_state.get(
            "last_marks", {}
        )
    )

    data = {}
    results = []

    for symbol in selected:
        for strategy, interval in [
            ("swing", "4h"),
            ("day", "15m")
        ]:
            try:
                df = get_candles(
                    symbol, interval
                )

                if df.empty:
                    continue

                data[(symbol, strategy)] = df

                marks[symbol] = float(
                    df.close.iloc[-1]
                )

            except Exception as exc:
                st.error(
                    f"{symbol} {interval}: "
                    f"falha na coleta ({exc})"
                )

    account.roll_day(marks)

    for (symbol, strategy), df in data.items():
        s = signal(df, strategy)

        candle_id = (
            symbol,
            strategy,
            s.get("candle_time")
        )

        if candle_id not in st.session_state.processed:

            if (symbol, strategy) in account.positions:
                events = account.check_exits(
                    symbol,
                    float(df.low.iloc[-1]),
                    float(df.high.iloc[-1]),
                    marks,
                    strategy=strategy
                )

                for event in events:
                    st.info(event)

            if s["action"] == "BUY":
                result = account.buy(
                    symbol,
                    strategy,
                    s["price"],
                    marks
                )

                st.info(result)

            st.session_state.processed.add(
                candle_id
            )

        results.append({
            "Par": symbol,
            "Estratégia": strategy,
            "Sinal": s["action"],
            "Preço USDT": s.get("price"),
            "RSI": s.get("rsi"),
            "Candle fechado": s.get(
                "candle_time"
            )
        })

    st.session_state.last_results = results
    st.session_state.last_marks = marks
    st.session_state.market_frames = data

# ==========================================
# PAINEL GERENCIAL
# ==========================================

marks = st.session_state.get(
    "last_marks", {}
)

a, b, c = st.columns(3)

a.metric(
    "Caixa (USDT)",
    f"{account.cash_usdt:.2f}"
)

b.metric(
    "Patrimônio marcado (USDT)",
    f"{account.equity(marks):.2f}"
)

c.metric(
    "Posições abertas",
    str(len(account.positions))
)

st.subheader("Radar")

st.dataframe(
    pd.DataFrame(
        st.session_state.get(
            "last_results", []
        )
    ),
    use_container_width=True
)

st.subheader("Posições simuladas")

st.dataframe(
    pd.DataFrame([
        vars(p)
        for p in account.positions.values()
    ]),
    use_container_width=True
)

st.subheader("Operações encerradas")

st.dataframe(
    pd.DataFrame(account.trades),
    use_container_width=True
)

# ==========================================
# FW CRYPTO AI — ASSISTENTE
# ==========================================

st.divider()

st.subheader("🤖 FW CRYPTO AI")

st.caption(
    "Assistente gratuito baseado em regras. "
    "Utiliza candles carregados no radar. "
    "Não executa ordens reais."
)

strategy_ai = st.radio(
    "Estratégia para análise",
    ["swing", "day"],
    horizontal=True,
    format_func=lambda value: (
        "Swing Trade (4h)"
        if value == "swing"
        else "Day Trade (15min)"
    )
)

frames = st.session_state.get(
    "market_frames", {}
)

chat_data = {
    symbol: df
    for (symbol, strategy), df
    in frames.items()
    if strategy == strategy_ai
}

if not chat_data:
    st.info(
        "Atualize o radar antes de solicitar "
        "análises de preços ao assistente."
    )

for message in st.session_state.crypto_chat:
    with st.chat_message(
        message["role"]
    ):
        st.markdown(
            message["content"]
        )

question = st.chat_input(
    "Ex.: Analise BTC, suporte da GRT..."
)

if question:
    st.session_state.crypto_chat.append({
        "role": "user",
        "content": question
    })

    try:
        answer = responder(
            question,
            dados=chat_data,
            estrategia=strategy_ai
        )

    except Exception as exc:
        answer = (
            "Não foi possível analisar "
            f"a pergunta: {exc}"
        )

    st.session_state.crypto_chat.append({
        "role": "assistant",
        "content": answer
    })

    st.rerun()

st.caption(
    "Protótipo manual. Não opera 24 horas, "
    "não faz backtest completo e não acessa "
    "saldos privados da Binance."
)
