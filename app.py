import streamlit as st
import pandas as pd
from engine import candles, signal, PaperAccount
from universe import discover_spot_usdt, top_liquid_pairs, FAVORITES
from portfolio import ASSETS, PortfolioPolicy

st.set_page_config(page_title='FW Binance Trader V1', layout='wide')
st.title('FW BINANCE TRADER V1')
st.warning('PAPER TRADING — nenhuma ordem real é enviada. O câmbio é uma entrada manual, não uma cotação.')
fx = st.number_input('BRL por 1 USDT (informar cotação de referência)', min_value=0.01, value=5.0, step=0.05)
if 'account' not in st.session_state:
    st.session_state.account = PaperAccount(brl_per_usdt=fx)
account = st.session_state.account
if abs(fx-account.brl_per_usdt)>0.000001:
    st.info('O câmbio inicial está fixado na conta desta sessão. Reinicie a simulação para alterá-lo.')
if st.button('Reiniciar simulação'):
    st.session_state.account = PaperAccount(brl_per_usdt=fx)
    st.rerun()
@st.cache_data(ttl=3600)
def get_universe():
    return discover_spot_usdt()

@st.cache_data(ttl=300)
def get_liquid(universe, n, minimum):
    return top_liquid_pairs(universe, limit=n, min_quote_volume=minimum)

try:
    universe = get_universe()
except Exception as exc:
    st.error(f'Não foi possível atualizar catálogo Binance: {exc}. Usando favoritos para visualização.')
    universe = FAVORITES
st.caption(f'{len(universe)} pares USDT Spot disponíveis no catálogo consultado; não significa que todos serão analisados simultaneamente.')
mode = st.radio('Modo do radar', ['Favoritos', 'Mais líquidos', 'Seleção manual'], horizontal=True)
if mode == 'Favoritos':
    defaults = [s for s in FAVORITES if s in universe]
elif mode == 'Mais líquidos':
    scan_limit = st.slider('Máximo de pares por atualização', 5, 50, 20, 5)
    min_volume = st.number_input('Volume mínimo 24h (USDT)', min_value=0.0, value=1_000_000.0, step=500_000.0)
    try:
        defaults = get_liquid(tuple(universe), scan_limit, min_volume)
    except Exception as exc:
        st.warning(f'Falha ao consultar volumes: {exc}')
        defaults = [s for s in FAVORITES if s in universe]
else:
    defaults = []
selected = st.multiselect('Pares a analisar (máximo 50 por atualização)', universe, default=defaults, max_selections=50)
st.caption('O catálogo inclui todos os pares elegíveis, mas cada atualização limita a coleta para evitar excesso de requisições. Apenas pares USDT nesta versão.')
st.sidebar.header('Proteção futura da carteira')
st.sidebar.info('Apenas planejamento. Não lê saldos reais e não envia ordens.')
if 'policy' not in st.session_state:
    st.session_state.policy = PortfolioPolicy()
policy = st.session_state.policy
for asset in sorted(set(ASSETS + [symbol[:-4] for symbol in selected])):
    current = float(policy.protected_minimum.get(asset, 0))
    minimum = st.sidebar.number_input(f'{asset}: saldo mínimo protegido', min_value=0.0, value=current, format='%.8f', key=f'protected_{asset}')
    from decimal import Decimal
    policy.protected_minimum[asset] = Decimal(str(minimum))
st.sidebar.error('EXECUÇÃO REAL BLOQUEADA NO CÓDIGO')
run = st.button('Atualizar radar e simular candles fechados')
if run:
    marks = {}
    data = {}
    for symbol in selected:
        for strategy, interval in [('swing','4h'),('day','15m')]:
            try:
                df = candles(symbol, interval)
                if df.empty: continue
                data[(symbol,strategy)] = df
                marks[symbol] = float(df.close.iloc[-1])
            except Exception as exc:
                st.error(f'{symbol} {interval}: falha na coleta ({exc})')
    account.roll_day(marks)
    # Do not repeat orders on repeated refreshes of the same closed candle.
    if 'processed' not in st.session_state: st.session_state.processed = set()
    results = []
    for (symbol,strategy), df in data.items():
        s = signal(df, strategy)
        candle_id = (symbol, strategy, s.get('candle_time'))
        if candle_id not in st.session_state.processed:
            # A posição só é avaliada pelo timeframe da sua estratégia.
            if (symbol, strategy) in account.positions:
                for event in account.check_exits(symbol, float(df.low.iloc[-1]), float(df.high.iloc[-1]), marks):
                    st.info(event)
            if s['action'] == 'BUY': st.info(account.buy(symbol, strategy, s['price'], marks))
            st.session_state.processed.add(candle_id)
        results.append({'Par':symbol,'Estratégia':strategy,'Sinal':s['action'],
                        'Preço USDT':s.get('price'),'RSI':s.get('rsi'),'Candle fechado':s.get('candle_time')})
    st.session_state.last_results = results
    st.session_state.last_marks = marks
marks = st.session_state.get('last_marks', {})
a,b,c = st.columns(3)
a.metric('Caixa (USDT)',f'{account.cash_usdt:.2f}')
b.metric('Patrimônio marcado (USDT)',f'{account.equity(marks):.2f}')
c.metric('Posições abertas',str(len(account.positions)))
st.subheader('Radar')
st.dataframe(pd.DataFrame(st.session_state.get('last_results', [])), use_container_width=True)
st.subheader('Posições simuladas')
st.dataframe(pd.DataFrame([vars(p) for p in account.positions.values()]), use_container_width=True)
st.subheader('Operações encerradas')
st.dataframe(pd.DataFrame(account.trades), use_container_width=True)
st.caption('Protótipo: atualiza somente ao clicar; não é serviço 24h, não faz backtest e não usa dados privados da conta Binance.')
