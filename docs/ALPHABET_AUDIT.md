# Auditoria de prontidão da avaliação — Alphabet

Data: 10 de novembro de 2026. Conclusão: **reconciliação factual efetuada; avaliação financeira não aprovada**. O dashboard pode ser publicado como monitorização, mantendo fair values e sinais bloqueados. Nenhum campo de aprovação foi ativado.

## Evidência original

- [10-Q de 30/09/2026, accession 0001652044-26-000084](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000084/goog-20260930.htm): balanço p. 4, cash flow p. 9, Nota 4 (locações), Nota 6 (dívida), Notas 11–12 (capital e EPS), MD&A de liquidez/CapEx.
- [10-K de 31/12/2025, accession 0001652044-26-000018](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm): demonstração consolidada de cash flow, exercícios 2023–2025.
- Os documentos completos foram descarregados diretamente da SEC. Os hashes SHA-256, URLs e reconciliações constam de `data/alphabet_audit.json`. Valores abaixo em **milhões de USD**, salvo ações. Não é um parecer de auditoria independente nem uma aprovação de pressupostos.

## 1. Dívida e caixa

| Rubrica em 30/09/2026 | Valor | Confirmação |
| --- | ---: | --- |
| Dívida de longo prazo não corrente | 125.102 | Nota 6 e balanço |
| Parcela corrente | 1.016 | Nota 6; incluída em passivos correntes acumulados |
| Total contabilístico de notes/dívida | 126.118 | 125.102 + 1.016 |
| Caixa e equivalentes | 56.334 | Balanço e cash flow |
| Dívida menos apenas caixa | 69.784 | Reconciliação aritmética, exclui locações |
| Locações financeiras correntes | 1.053 | Nota 4; não incluídas na tag LongTermDebtCurrent |
| Locações financeiras não correntes | 2.652 | Nota 4; em outros passivos de longo prazo |
| Total de locações financeiras | 3.705 | Nota 4 |
| Dívida menos caixa, incluindo finance leases | 73.489 | Alternativa de âmbito, ainda não aprovada |
| Locações operacionais, total | 20.508 | Nota 4; não somar automaticamente sem ajustar o cash flow |

A tabela da Nota 6 reconcilia valor facial de 127.485 menos custos/desconto de 1.110 e ajustes de cobertura de 257 = 126.118. Não misturar valor facial, contabilístico e fair value da dívida. Commercial paper e linhas revolving não tinham montantes utilizados na data; esta ausência foi confirmada no texto original, não inferida de uma tag em falta. A capacidade disponível não é dívida já contraída.

O balanço apresenta ainda 208.764 de marketable securities e 135.230 de non-marketable securities. Não equivalem automaticamente a caixa operacional disponível: requerem separar dívida/equity, riscos, impostos e ativos não operacionais. Adicionar o valor destes investimentos ao valor de operações sem retirar o seu rendimento do cash flow pode duplicar valor. Os números de dívida líquida acima **não são uma ponte para equity aprovada**.

**Achado:** o cálculo anterior exclui finance leases; chamar-lhe dívida líquida integral seria incompleto. A avaliação passa a bloquear explicitamente finance leases até existir uma metodologia implementada e testada. A Nota 6 também menciona financiamento Waymo posterior ao balanço; eventos subsequentes precisam de tratamento datado, sem os somar automaticamente ao snapshot de setembro.

## 2. Classes e diluição

O balanço, em milhões de ações, confirma A = **5.888**, B = **828**, C = **5.578**; soma = **12.294**. O valor consolidado de Companyfacts reconcilia com o balanço. GOOGL representa classe A, mas o denominador económico não pode incluir apenas essa classe. A Nota 12 indica direitos económicos de liquidação/dividendos idênticos entre A/B/C, com diferenças de voto.

A média diluída de EPS do trimestre (12.368 milhões) não é o saldo final de ações (12.294 milhões), nem uma previsão de diluição futura. Não substituir automaticamente um pelo outro ou duplicar a conversão B→A ao somar classes.

**Achado material:** a Nota 11 apresenta preferenciais obrigatoriamente convertíveis, séries A/B, taxa anual de 6,25%, conversão prevista para maio de 2029, dividendos que podem ser pagos em ações e capped calls. O balanço apresenta cerca de 19 milhões de preferenciais, arredondados, e valor contabilístico de 18.023. A divulgação refere 385 milhões de depositary shares, cada uma representando 1/20 de uma preferencial. Não confundir depositary shares com ações preferenciais ou ações ordinárias. O programa ATM e SBC acrescentam diluição potencial; não presumir recompras futuras para a compensar.

O modelo atual não deduz uma claim preferencial nem projeta conversão/dividendos/capped calls. Assim, **não é suficiente aprovar os números A/B/C**. O novo bloqueio `UNSUPPORTED_PREFERRED_STOCK` não é removível por um simples checkbox de revisão: requer evolução do modelo após decisão humana.

## 3. FCF: reconstrução sem extrapolar lucros extraordinários

| Período | OCF | CapEx pago | OCF − CapEx |
| --- | ---: | ---: | ---: |
| Ano 2025 | 164.713 | 91.447 | 73.266 |
| Nove meses 2025 | 112.311 | 63.596 | 48.715 |
| Nove meses 2026 | 127.149 | 131.953 | −4.804 |
| TTM terminado em setembro 2026 | 179.551 | 159.804 | **19.747** |

FCF TTM = 73.266 − 4.804 − 48.715 = 19.747. A reconstrução bate certo com o 10-K e os comparativos do 10-Q. **Isto valida a aritmética e a proveniência, não a sustentabilidade do FCF.**

O lucro líquido de nove meses de 2026 é 201.239, mas o cash flow já reverte 126.755 de ganhos líquidos sobre títulos de dívida/equity. O MD&A identifica ganhos não realizados em investimentos como causa importante do aumento de resultados. Não crescer o lucro extraordinário como se fosse caixa recorrente; também não subtrair esses ganhos uma segunda vez ao OCF já reconciliado.

O cash flow inclui add-back de SBC de 23.338, alterações de capital circulante e impostos. CapEx pago não equivale a todo o investimento económico: há equipamento em passivos acumulados e ativos adquiridos por locação. A Nota 4 divulga 1.950 de pagamentos de capital de finance leases nos nove meses de 2026 e 994 de pré-pagamentos de locações ainda não iniciadas. Não ignorar estes fluxos nem contá-los duas vezes. O MD&A prevê investimento de infraestrutura em 2026 significativamente superior a 2025; não substituir silenciosamente o FCF TTM pelo FCF anual maior ou classificar todo o CapEx de IA como extraordinário.

**FCF normalizado permanece `null`.** É necessária uma ponte explícita entre OCF/CapEx, componentes não recorrentes, investimento sustentável, SBC, impostos, financiamento e fluxo disponível para os titulares relevantes.

## 4. Pressupostos e método: decisões humanas pendentes

| Decisão | Fundamentação / trabalho necessário antes de desbloquear |
| --- | --- |
| FCFF/WACC ou FCFE/custo do equity | OCF US GAAP já inclui juros; subtrair dívida a um proxy após juros pode tornar a ponte incoerente. Escolher o método, ajustar juros/impostos e testar a ponte para equity. |
| Locações | Definir capitalização e tratamento dos fluxos de locação, preservando consistência entre numerador e dívida. Os 73.489 são apenas uma alternativa aritmética. |
| Preferenciais e diluição | Modelar claim/dividendos ou conversão, datas, denominador e capped calls; não deduzir a claim e aplicar simultaneamente a mesma diluição sem fundamento. Reconciliar SBC/ATM. |
| FCF sustentável | Aprovar ajustes identificáveis e a trajetória de CapEx/working capital/impostos. Nenhum valor normalizado foi escolhido automaticamente. |
| Ativos não operacionais | Decidir quais investimentos adicionar, líquidos de obrigações/impostos, eliminando rendimentos duplicados no cash flow. |
| Crescimento e desconto | Os cenários atuais (5/10/15% de crescimento; 11/9/8% desconto; 2/2,5/3% terminal) são hipóteses editoriais, não dados SEC. Justificar custo de capital, risco e maturidade; fazer sensibilidade. |

É possível publicar já a monitorização sem decidir estes temas. O ficheiro `data/valuation_policy.json` permanece com `valuation_enabled: false`; a revisão permanece não aprovada; existem bloqueios adicionais de capacidade do modelo. OCI, OCF, FCF TTM e FCF normalizado não são sinónimos. Não há recomendação de compra nesta auditoria.
