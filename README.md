# Investment Monitor 2.0

Monitor de investigação, sem execução de ordens. Preserva carteira/watchlist, cotações indicativas e resumo semanal. A Alphabet usa recolha gratuita da SEC e um DCF com três cenários; dados insuficientes bloqueiam fair values, margens e oportunidades. Não foram adicionadas APIs pagas. O comentário Anthropic existente fica desativado por defeito; requer `ENABLE_PAID_COMMENTARY=1` e chave para utilização explicitamente autorizada.

## Executar e validar

Python 3.12, biblioteca standard, sem dependências de produção:

```sh
python -m unittest discover -s tests -v
OFFLINE_TEST=1 REPORT_MODE=daily python -m src.monitor
```

O modo offline não faz pedidos de rede nem envia Telegram, mesmo com credenciais presentes. Produz um dashboard com valores indisponíveis, não cotações fictícias. Para execução real: `REPORT_MODE=daily python -m src.monitor`, com as variáveis abaixo fornecidas pelo ambiente. Não colocar credenciais nos ficheiros. O workflow executa os testes antes de recolher/publicar dados.

## Configuração existente

Secrets de GitHub Actions utilizados: `SEC_USER_AGENT` (identificação e email de contacto exigidos pela SEC), `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. A aplicação não lê nem imprime os seus valores. Secrets só são resolvidos pelo GitHub no runner. Sem contacto SEC válido, a recolha é bloqueada; sem Telegram configurado não há envio. Uma entrega Telegram falhada não avança o estado e faz a execução falhar, permitindo repetir.

`DASHBOARD_URL` é uma variável opcional de Actions; por defeito aponta para <https://markinhofr.github.io/investment-monitor/>. `data/portfolio.json` mantém os tickers e posições existentes. ETFs com bolsa/ticker por confirmar continuam sem cotações ou sinais. Fair values manuais de outros títulos exigem `verified: true`, `valuation_ready: true`, moeda, valor positivo finito, `source_url` e `as_of` recente (até 120 dias).

## Fontes, reconciliação e revisão financeira

SEC: <https://data.sec.gov/api/xbrl/companyfacts/CIK0001652044.json>. Seleciona 10-K/10-Q, unidade USD ou shares, data do período, data de entrega e accession. Para cada período/tag prefere a entrega mais recente, incluindo comparativos revistos. A fonte original e componentes ficam no relatório estruturado; isto é validação programática, não auditoria.

- FCF TTM = OCF anual − CapEx anual + FCF YTD atual − FCF YTD comparável anterior. Na ausência de trimestrais compatíveis, pode usar o último ano completo, sujeito ao mesmo limite de antiguidade (150 dias). Cada componente tem de coincidir em período e entrega, e a soma é reconciliada. Falta de dados nunca equivale a zero.
- Dívida líquida = dívida financeira corrente + não corrente − caixa/equivalentes, todos na mesma data e entrega. Não se subtraem automaticamente títulos negociáveis. Tags alternativas podem incluir locações; a revisão confirma âmbito e ausência de dupla contagem. Dívida não apresentada explicitamente bloqueia a avaliação.
- Ações: `CommonStockSharesOutstanding`, nunca média diluída de resultados. Companyfacts não resolve por si só a agregação das classes A/B/C: exige confirmação no relatório original. Não se presume que ações GOOGL representem todo o capital.
- Lucro líquido não é convertido em FCF. Ganhos extraordinários contabilísticos não são projetados. Efeitos extraordinários no próprio OCF exigem revisão e justificação do FCF normalizado.

`data/alphabet_review.json` contém a revisão financeira, inicialmente **não aprovada**: período, accession, URL SEC Archives, responsável, data, confirmação de todas as classes, âmbito da dívida, revisão de extraordinários, aprovação dos pressupostos, `normalized_fcf` e justificação. Os dados recolhidos são automáticos; este registo é uma decisão financeira humana e não deve ser preenchido com números inventados. A revisão só vale para a entrega/período exatos e durante 120 dias; uma nova entrega bloqueia novamente o DCF. O FCF normalizado deve ser positivo e não superior ao TTM, uma restrição conservadora deliberada. Valores normalizados superiores exigiriam evolução e nova revisão da metodologia.

## DCF e dashboard

DCF de cinco anos, FCF normalizado projetado, terminal de Gordon, desconto, subtração da dívida líquida e divisão pelo total de ações. Cenários (`src/dcf_report.py`):

| Cenário | Crescimento anual | Desconto | Crescimento terminal |
| --- | --- | --- | --- |
| Pessimista | 5% | 11% | 2% |
| Base | 10% | 9% | 2,5% |
| Otimista | 15% | 8% | 3% |

São hipóteses editoriais, não previsões da SEC. Exigem aprovação na revisão. OCF menos CapEx é um proxy simplificado de fluxo de caixa, não FCFF puro; não modela separadamente juros, stock based compensation, diluição futura, ciclos de CapEx ou impostos normalizados. O total de ações agrega direitos económicos por classe sob revisão. Não representa garantia de valor nem recomendação.

Margem de segurança = `(fair value − cotação) / fair value × 100`. Só é calculada com avaliação pronta e cotação positiva, finita, na mesma moeda e até cinco dias de antiguidade. 25% indica investigar compra; 15% estudar entrada. O dashboard mostra preço/data/fonte, fair value base, margem, receitas e lucro anuais com período, FCF TTM separado do normalizado, última atualização e histórico. A página DCF mostra cenários, margens, taxas, fonte, revisão e bloqueios. `docs/latest.json`, `docs/dcf_alphabet.json` e `docs/history.json` fornecem detalhe auditável. Histórico limitado às últimas 366 execuções (não necessariamente 366 dias).

## Telegram e persistência

Envia link do dashboard, novo accession financeiro SEC, mudanças de estado da validação, oportunidades, revisão de fair value de pelo menos 5%, movimentos de preço acumulados de pelo menos 3% e resumo semanal. Não pesquisa notícias externas nem estima a data futura de earnings. O aviso de resultados significa nova demonstração SEC disponível, não anúncio em tempo real.

`data/notification_state.json` guarda o último relatório enviado com sucesso e o identificador do resumo semanal. Comparação com esse estado evita repetir o mesmo alerta, inclusive em reexecuções. Falhas de entrega mantêm o estado anterior. Existe uma janela residual: se o Telegram aceitar uma mensagem e a ligação cair antes da confirmação, ou se o commit falhar, a repetição pode duplicar a mensagem; Telegram não oferece chave de idempotência para sendMessage. Não é uma garantia de entrega exatamente uma vez. O workflow serializa execuções.

## GitHub Actions, Lisboa e Pages

Diário às **22:30 de Lisboa**, semanal ao domingo **10:30**, com `zoneinfo` para verão/inverno. O cron dispara ao minuto 30 UTC de cada hora e o código filtra a janela local; atrasos para fora da janela podem perder a execução, e GitHub não garante pontualidade. `workflow_dispatch` permite executar `daily`, `weekly` ou `auto` escolhendo a branch **investment-v2**.

**Todas as escritas automáticas são exclusivamente em `investment-v2`. O workflow não faz push em main nem merge.** PRs executam apenas testes, sem secrets e sem atualização do dashboard.

Limitações de ativação verificadas nesta implementação:

1. GitHub só agenda workflows que existem na branch predefinida (atualmente `main`). Como esta alteração permanece exclusivamente em `investment-v2`, o novo agendamento só pode ficar ativo após decisão do proprietário sobre integração/configuração da branch predefinida. O cron anterior em main não foi alterado por este trabalho.
2. Pages está atualmente configurado para `main:/docs`. Os ficheiros gerados em `investment-v2` ficam prontos para revisão, mas não substituem o site público enquanto a origem de Pages ou a integração não for decidida. O link Telegram refere o site publicado, que pode ainda mostrar a versão anterior. Não se alterou essa configuração automaticamente.
3. A API disponível não permitiu listar os nomes dos Secrets (403). Não se assume que estejam configurados; devem ser confirmados por uma execução no runner.

Para confirmar: Actions → **Investment monitoring v2** → Run workflow → branch `investment-v2` → `daily`. Verificar testes, estado SEC/DCF no JSON, mensagem Telegram e commit apenas na branch autorizada. Reexecutar sem alterações deve suprimir alertas repetidos. Para validar visualmente antes de Pages, executar `python -m http.server 8000 --directory docs` e abrir o endereço local. Abrir `dcf.html` por HTTP, pois usa fetch de JSON.

## Manutenção e limites

Rever os dados no 10-Q/10-K original a cada nova entrega, classes de ações, novas tags SEC, dívida, extraordinários e pressupostos. Investigar `DATA_UNAVAILABLE` e `errors` sem reutilizar silenciosamente o fair value anterior. Yahoo Chart é público e não oficial, pode limitar/falhar e não tem SLA; preços são atrasados/último fecho. A ausência de dados não desencadeia oportunidades. SEC também pode responder 403/429; uma execução posterior volta a tentar. Não há API paga de substituição.

O dashboard e os JSON são públicos quando publicados. Não adicionar quantidades/custos privados. Não há corretora, P&L fiável sem posições confirmadas, notícias gerais, dados fundamentais automatizados das outras empresas ou armazenamento privado. Actions/Pages estão sujeitos aos limites e políticas do GitHub.
