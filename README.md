# FW Binance Trader V1 — Protótipo

**Somente simulação.** Não há autenticação, API key ou envio de ordens.

## Executar

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

O painel usa o endpoint público `/api/v3/klines` da Binance Spot. Requer internet e disponibilidade do endpoint na sua região.

## Regras da versão
- Capital de referência: R$ 1.000 convertido para USDT por câmbio manual, fixado no início da sessão.
- Swing: EMA21/50 em 4h; Day: EMA9/21 em 15min; cruzamento de alta com RSI 45–70 em candle fechado.
- Stop de 2%, alvo de 4%; risco planejado até 0,5% do patrimônio por entrada, considerando taxas estimadas.
- Até 3 posições, limite diário de perda marcado de 2%, taxa simulada de 0,1% por lado e slippage de 0,05%.
- Stops e alvos verificados apenas quando o botão é acionado; movimentos intermediários podem ser perdidos.
- Estado guardado apenas na sessão Streamlit, não persistido após reinício.

## Antes de operação real
Persistir estado em SQLite/PostgreSQL; criar scheduler e processamento incremental candle a candle; conferir filtros de quantidade/notional e taxas reais por par; implementar backtest sem lookahead, custos e cenários adversos; atualizar preço e P&L continuamente; definir timezone de corte diário; incluir reconciliação de ordens, kill switch, logs, proteção contra duplicatas e testes em ambiente isolado. A execução real deverá ser um módulo separado, habilitado somente após aprovação explícita.

**Aviso:** não existe garantia de lucro; o risco de stop não é um teto absoluto de perda.

## Atualização: carteira protegida e oito ativos
Monitoramento público: GRT, PEPE, BTC, ETH, XRP, SOL, ADA e DOGE, todos nos pares USDT. A aba lateral permite registrar um saldo mínimo protegido **para planejamento**, sem acessar a carteira real. O módulo `portfolio.py` fornece `available_to_sell` e `validate_sell` para uma integração futura. A classe `RealOrderGateway` bloqueia qualquer ordem real, inclusive após configurar mínimos e permissões.

**Limitações de segurança:** o simulador atual não tem conexão autenticada, não tem persistência, não executa continuamente, não reproduz a carteira real e não é um backtest rigoroso. A lógica de saídas com candles não deve ser interpretada como execução garantida. Os limites e proteções devem ser revalidados antes de qualquer implementação de negociação real. A cotação BRL/USDT é inserida manualmente. Nunca cole chaves de API no código, GitHub ou chat.

## Executar
`pip install -r requirements.txt && streamlit run app.py`

## Testes
`python -m unittest -v test_safety.py`

## Radar ampliado — catálogo Spot Binance
O módulo `universe.py` consulta `exchangeInfo` e lista dinamicamente os pares USDT com negociação Spot habilitada. O painel permite **Favoritos**, **Mais líquidos** (com filtro de volume em USDT nas últimas 24 horas) e **Seleção manual**. O catálogo é armazenado em cache por uma hora; volumes por cinco minutos. Para limitar requisições, o usuário analisa até 50 pares por atualização, não todos simultaneamente. Somente pares USDT nesta versão; não é um scanner universal de todos os pares/mercados. A seleção e os saldos mínimos são apenas planejamento/simulação. Execução real permanece bloqueada. A lista disponível depende da API pública, região e condições de mercado.
