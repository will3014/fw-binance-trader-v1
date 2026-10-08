
"""
FW CRYPTO AI V1
Assistente gratuito baseado em regras.
Sem ordens reais e sem API paga de IA.
"""

import re
import unicodedata
import pandas as pd

FAVORITOS = [
    "BTC", "ETH", "SOL", "XRP",
    "GRT", "PEPE", "ADA", "DOGE",
]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return texto


def identificar_moeda(pergunta, disponiveis=None):
    texto = normalizar(pergunta).upper()
    moedas = disponiveis or FAVORITOS

    for moeda in sorted(moedas, key=len, reverse=True):
        base = moeda.upper().removesuffix("USDT")
        padrao = rf"(?<![A-Z0-9]){re.escape(base)}(?:USDT)?(?![A-Z0-9])"
        if re.search(padrao, texto):
            return base + "USDT"

    return None


def indicadores(df):
    if df is None or len(df) < 55:
        return None

    dados = df.copy()
    for coluna in ["high", "low", "close"]:
        dados[coluna] = pd.to_numeric(
            dados[coluna], errors="coerce"
        )

    dados = dados.dropna(subset=["high", "low", "close"])

    if len(dados) < 55:
        return None

    fechamento = dados["close"]

    ema9 = fechamento.ewm(
        span=9, adjust=False
    ).mean()

    ema21 = fechamento.ewm(
        span=21, adjust=False
    ).mean()

    ema50 = fechamento.ewm(
        span=50, adjust=False
    ).mean()

    delta = fechamento.diff()
    ganho = delta.clip(lower=0).ewm(
        alpha=1 / 14, adjust=False
    ).mean()

    perda = (-delta.clip(upper=0)).ewm(
        alpha=1 / 14, adjust=False
    ).mean()

    if perda.iloc[-1] == 0:
        rsi = 100.0 if ganho.iloc[-1] > 0 else 50.0
    else:
        rs = ganho.iloc[-1] / perda.iloc[-1]
        rsi = 100 - 100 / (1 + rs)

    # Exclui o candle mais recente dos níveis.
    historico = dados.iloc[-21:-1]

    suporte = float(historico["low"].min())
    resistencia = float(historico["high"].max())
    preco = float(fechamento.iloc[-1])

    tendencia = (
        "ALTA" if ema21.iloc[-1] > ema50.iloc[-1]
        else "BAIXA"
    )

    return {
        "preco": preco,
        "ema9": float(ema9.iloc[-1]),
        "ema21": float(ema21.iloc[-1]),
        "ema50": float(ema50.iloc[-1]),
        "rsi": float(rsi),
        "suporte": suporte,
        "resistencia": resistencia,
        "tendencia": tendencia,
    }


def formatar_preco(valor):
    if valor < 0.001:
        return f"{valor:.10f}"
    if valor < 1:
        return f"{valor:.6f}"
    return f"{valor:.4f}"


def analisar_mercado(simbolo, df, estrategia="swing"):
    info = indicadores(df)

    if info is None:
        return (
            "Histórico insuficiente para analisar "
            f"{simbolo}. Nenhuma entrada recomendada."
        )

    preco = info["preco"]
    suporte = info["suporte"]
    resistencia = info["resistencia"]
    rsi = info["rsi"]

    if preco <= 0 or suporte <= 0:
        return "Dados de preço inválidos."

    favoravel = (
        info["tendencia"] == "ALTA"
        and 45 <= rsi <= 70
        and preco > info["ema21"]
    )

    risco = preco - suporte
    alvo = preco + 2 * risco

    resposta = [
        f"FW CRYPTO AI | {simbolo}",
        f"Estratégia: {estrategia.upper()}",
        "",
        f"Preço: {formatar_preco(preco)} USDT",
        f"Tendência: {info['tendencia']}",
        f"RSI: {rsi:.1f}",
        f"EMA 9: {formatar_preco(info['ema9'])}",
        f"EMA 21: {formatar_preco(info['ema21'])}",
        f"EMA 50: {formatar_preco(info['ema50'])}",
        "",
        f"Suporte: {formatar_preco(suporte)}",
        f"Resistência: {formatar_preco(resistencia)}",
        "",
    ]

    if favoravel and risco > 0:
        resposta.extend([
            "CENÁRIO: tendência favorável.",
            "Aguardar confirmação de entrada.",
            f"Stop técnico indicativo: {formatar_preco(suporte)}",
            f"Alvo teórico 2R: {formatar_preco(alvo)}",
        ])
    else:
        resposta.extend([
            "CENÁRIO: AGUARDAR.",
            "Os critérios de tendência, RSI ou "
            "posição do preço não estão alinhados.",
        ])

    resposta.extend([
        "",
        "Análise educativa, não é ordem de compra.",
        "Taxas, liquidez e slippage devem ser avaliados.",
    ])

    return "\n".join(resposta)


def responder(pergunta, dados=None, estrategia="swing"):
    """
    dados: dicionário { 'BTCUSDT': dataframe, ... }
    Os candles devem estar fechados.
    """
    dados = dados or {}
    texto = normalizar(pergunta)

    if any(p in texto for p in [
        "comprar", "entrada", "vender",
        "analise", "analisar", "suporte",
        "resistencia", "rsi", "tendencia",
    ]):
        simbolo = identificar_moeda(
            pergunta, list(dados.keys()) or FAVORITOS
        )

        if not simbolo:
            return (
                "Informe a moeda. Exemplo: "
                "'Analise BTC para Swing Trade'."
            )

        if simbolo not in dados:
            return (
                f"Não tenho candles de {simbolo} "
                "nesta sessão. Atualize o radar."
            )

        return analisar_mercado(
            simbolo, dados[simbolo], estrategia
        )

    if "risco" in texto or "capital" in texto:
        return (
            "Capital inicial simulado: R$ 1.000.\n"
            "Risco planejado por operação: 0,5% (R$ 5).\n"
            "Limite diário planejado: 2% (R$ 20).\n"
            "Máximo: 3 posições simultâneas.\n"
            "Stops não garantem execução exata."
        )

    if "swing" in texto:
        return (
            "Swing Trade: operações de vários dias. "
            "Priorizar tendência, EMA 21/50, "
            "RSI e suportes no gráfico de 4 horas."
        )

    if "day trade" in texto:
        return (
            "Day Trade: operações intradiárias. "
            "Priorizar EMA 9/21, volume, "
            "suporte e resistência no gráfico de 15 minutos."
        )

    if "oi" == texto.strip() or "ola" in texto:
        return (
            "Olá! Sou o FW CRYPTO AI.\n"
            "Posso explicar indicadores e analisar "
            "moedas carregadas no radar.\n"
            "Exemplo: Analise GRT."
        )

    return (
        "Sou o FW CRYPTO AI V1, baseado em regras.\n"
        "Você pode perguntar:\n"
        "- Analise BTC\n"
        "- Qual o suporte da GRT?\n"
        "- Explique Swing Trade\n"
        "- Qual meu limite de risco?\n"
        "Ainda não tenho conversa livre como o ChatGPT."
    )
