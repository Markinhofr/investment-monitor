# Alphabet — modelo FCFF/WACC para revisão financeira

Data da preparação: **11/11/2026**. Metodologia principal aprovada pelo proprietário: **FCFF/WACC**. Os números normalizados, taxas, cenários e políticas de tratamento abaixo **não estão aprovados**. O modelo é um módulo de investigação separado; não altera o monitor, não publica avaliações e nunca muda `data/valuation_policy.json`.

## Fontes, datas e proveniência

| Fonte oficial | Utilização |
| --- | --- |
| [10-K, exercício 2025](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm), accession 0001652044-26-000018, entregue em 05/02/2026 | Balanço, demonstração de resultados e cash flow anual de 2025 |
| [10-Q, setembro 2026](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000084/goog-20260930.htm), accession 0001652044-26-000084, entregue em 29/10/2026 | Nove meses 2026/2025; Notas 4, 6, 8, 11 e 12; balanço em 30/09/2026 |
| [US Treasury — taxas oficiais](https://home.treasury.gov/resource-center-data-chart-center/interest-rates) | Referência para Rf nominal USD com prazo consistente; nenhum valor foi selecionado automaticamente |
| Yahoo Chart GOOGL/GOOG, URLs e datas no ficheiro de inputs | Cotações indicativas gratuitas, não oficiais, sujeitas a falhas e atraso; não são dados SEC |

`data/fcff_sec_evidence.json` guarda SHA-256 de cada documento, tag iXBRL, contexto, unidade, escala/precisão, período, accession, URL e valor. A extração verifica CIK 1652044 e distingue dimensões A/B/C de números consolidados. Rejeita ambiguidade de valores, unidades incompatíveis, dados nil, formatos não suportados e conceitos/intervalos incompatíveis. Um registo `validated: true` significa apenas extração/reconciliação técnica: não aprova o âmbito contabilístico ou um pressuposto financeiro.

TTM de 01/10/2025 a 30/09/2026 = ano 2025 + nove meses 2026 − nove meses 2025. O motor reconcilia os componentes e os períodos, não aceita simplesmente um valor marcado como validado.

| Rubrica, milhões de USD | Ano 2025 | 9M2026 | 9M2025 | TTM |
| --- | ---: | ---: | ---: | ---: |
| Receita | 402.836 | 357.269 | 289.007 | 471.098 |
| EBIT reportado | 129.039 | 121.042 | 93.105 | 156.976 |
| OCF | 164.713 | 127.149 | 112.311 | 179.551 |
| Add-back SBC no cash flow | 24.953 | 23.338 | 17.882 | 30.409 |
| Depreciação PPE | 21.136 | 21.955 | 15.096 | 27.995 |
| Juros não operacionais reconhecidos | 736 | 2.778 | 438 | 3.076 |
| Juros capitalizados divulgados | 447 | 1.000 | 301 | 1.146 |
| Novos ROU em finance leases | 1.606 | 2.987 | 989 | 3.604 |
| CapEx pago | 91.447 | 131.953 | 63.596 | 159.804 |

A divulgação de juros capitalizados tem arredondamento material. Depreciação PPE não é automaticamente D&A operacional completo: há amortização de intangíveis de 920 em 9M2026 e 375 em 9M2025, mas a extração anual não encontrou um facto comparável. **Não se presumiu zero.** Juros reconhecidos de 3.076 TTM não são automaticamente juros pagos dentro do OCF; o valor completo de pagamentos continua em falta. Os 77 milhões de juros pagos de finance leases TTM são apenas uma componente, não substituem juros pagos totais.

## FCFF: rota principal e reconciliação independente

Proposta de normalização, a aprovar:

```text
EBIT normalizado = EBIT reportado + SBC reportado − custo económico SBC normalizado
                  + ajustes EBIT identificados, com sinal e fonte
Imposto operacional normalizado = max(EBIT normalizado, 0) × taxa operacional aprovada
NOPAT = EBIT normalizado − imposto operacional normalizado
CapEx próprio económico = CapEx sustentável pago + variação de CapEx próprio a pagar
                         − juros capitalizados incluídos no CapEx
CapEx económico = CapEx próprio económico + investimento líquido em finance leases
FCFF = NOPAT + D&A operacional − CapEx económico − ΔNWC operacional normalizado
       + outros ajustes operacionais após impostos aprovados
```

SBC já é custo em EBIT; o motor substitui o custo reportado pelo sustentável, sem o subtrair duas vezes. Confirmar que o add-back SBC do cash flow tem o mesmo âmbito do custo reconhecido em EBIT; capitalização/diferenças de âmbito precisam de mapeamento explícito. D&A exclui o add-back SBC.

A política proposta trata SBC como custo económico equivalente a caixa. Por isso não aplica também uma taxa de diluição futura para a mesma remuneração. A margem operacional de cada ano projetado deve já incluir esse custo, rendas operacionais e D&A. Diluição incremental de outros instrumentos exige reconciliação separada, líquida de proventos, identificando que não duplica os mesmos awards. Não se pressupõem recompras.

O investimento de finance leases inclui ativos ROU e ajustes de pré-pagamentos/âmbito aprovados. Não se substitui por amortizações de principal: principal é financiamento. Os juros capitalizados são retirados do CapEx apenas quando os inputs demonstram que estão incluídos nesse valor, evitando reintroduzir custos de financiamento no FCFF.

Rota independente:

```text
FCFF via OCF = OCF + juros pagos DENTRO do OCF, incluindo finance leases, × (1 − benefício fiscal)
               − rendimento não operacional recebido, após impostos
               − custo económico SBC normalizado − CapEx económico
               + ajustes OCF identificados e aprovados
```

Os ajustes OCF devem explicar separadamente impostos operacionais, capital circulante, outros não monetários e efeitos extraordinários. Não usar um ajuste para fechar arbitrariamente a diferença. A tolerância é um input aprovado, limitado a 0,1% do FCFF (mínimo USD 1); a diferença permanece visível e bloqueia o modelo se exceder a tolerância. Se a precisão das fontes não permitir reconciliar, procurar detalhe adicional em vez de aumentar ilimitadamente a tolerância.

O OCF já reverte os ganhos não monetários de investimentos divulgados no cash flow. Não deduzir esses ganhos novamente. EBIT exclui o resultado financeiro/não operacional. Normalizar investimento ou working capital exige uma ponte explícita; não substituir o FCF TTM pelo ano histórico mais favorável. Aquisições, intangíveis ou investimento fora de PPE que sejam necessários para sustentar a atividade exigem ajuste explícito; não são considerados automaticamente dispensáveis.

## WACC: custos e valores de mercado

```text
Ke = Rf USD + beta alavancado × prémio de risco acionista + prémio de risco adicional
V = valor de mercado ordinário E + dívida notes Dn + PV finance leases Dl + preferenciais P
WACC = E/V × Ke + Dn/V × Kn × (1 − Tn) + Dl/V × Kl × (1 − Tl) + P/V × Kp
```

- **E:** A × preço A + B × preço B/proxy revisto + C × preço C. Não usar apenas GOOGL nem duplicar B na conversão B→A. Os três preços devem ter a mesma data e até cinco dias de antiguidade relativamente à data de avaliação.
- **Rf:** prazo, moeda e base nominal consistentes com FCFF e terminal; taxa Treasury efetivamente datada, não um número escolhido pelo código.
- **Beta/ERP:** estimativa com janela, benchmark, frequência, alavancagem, metodologia e datas documentados. A SEC não fornece um beta prospetivo ou ERP. O motor requer beta anual por cenário e beta terminal revistos; não aplica Hamada automaticamente a uma estrutura híbrida sem aprovação.
- **Kn:** yield/retorno marginal da dívida vigente, não cupão histórico nem juros reconhecidos divididos por dívida final. O justo valor das notes em 30/09/2026 é 114.900 milhões; não o confundir com valor contabilístico 126.118. Usá-lo em novembro exige roll-forward explícito.
- **Kl:** custo das finance leases separado das notes e benefício fiscal próprio. As obrigações financeiras de locação são 3.705 milhões em setembro. Não adicionar esse passivo duas vezes se uma fonte agregada já o incluir.
- **P/Kp:** valor económico integral e retorno requerido das preferenciais híbridas, incluindo dividendos e conversão. O cupão de 6,25% não é automaticamente Kp; valor contabilístico de 18.023 milhões não é cotação de mercado.

O WACC inicial mostra todos os pesos/custos. O DCF utiliza uma estrutura temporal: cada cenário fornece pesos E/D/P e beta por ano. Na conversão obrigatória prevista para cerca de **15/05/2029**, o desconto do ano é dividido entre antes/depois do evento, segundo os dias de cada segmento. O peso P transfere-se para equity; não permanece na perpetuidade. O terminal exige P=0. As trajetórias de dívida/equity, yield e prémios constantes ou variáveis precisam de fundamentação; o modelo atual mantém yields/prémios aprovados constantes e permite beta, pesos e ajuste de risco por cenário. Não constitui uma previsão automática de refinanciamentos ou um modelo completo de opções.

A fonte prevê também conversão antecipada/especial e capped calls. A data usada é o caso-base contratual divulgado, não certeza. O método escolhido deduz uma **claim híbrida integral avaliada por fonte de mercado/análise aprovada**, em vez de tentar inferir o valor de opções a partir do book value. Caso essa avaliação não exista ou não cubra os termos relevantes, o modelo permanece bloqueado. Não há pricer autónomo de opções/preferenciais nesta implementação.

## Enterprise Value → ações ordinárias

```text
EV = soma dos FCFF anuais descontados pelos produtos de (1 + WACC anual)
     + terminal descontado pelos mesmos fatores
Excesso de caixa = caixa total − caixa mínima operacional
Equity antes das preferenciais = EV + excesso de caixa + investimentos líquidos de impostos
                                + fair value dos capped calls − notes a valor de mercado
                                − finance leases − minoritários − outras claims
Equity ordinário residual = equity antes das preferenciais − claim híbrida integral
Valor por ação = max(equity ordinário residual, 0) / (A + B + C + diluição incremental não duplicada)
Margem de segurança = (valor por ação − cotação A) / valor por ação × 100
```

O déficit de equity é apresentado separadamente, preservando a reconciliação antes do piso de responsabilidade limitada. Com valor por ação zero, a margem é indisponível. Caixa mínima, investimentos líquidos de impostos, minoritários (incluindo interesses em subsidiárias), contingências e capped calls exigem revisão: ausências não viram zero. Rendimento de investimentos não operacionais sai do FCFF se o ativo for adicionado separadamente, evitando dupla contagem.

No tratamento por claim integral, **não** se adicionam simultaneamente as ações da mesma conversão ao denominador. Capped calls entram como ativo revisto; não se usa ao mesmo tempo um abatimento de ações. Direitos económicos A/B/C são reconciliados com as Notas 11–12, separando saldo final de médias usadas no EPS. Os saldos de setembro são A=5.888, B=828, C=5.578 milhões, total 12.294 milhões.

## Cenários e sensibilidade

Os cenários pessimista, base e otimista têm cinco anos de crescimento de receita, margem EBIT após SBC económico, D&A/receita, CapEx próprio/receita, investimento de finance leases/receita e NWC/receita. Nenhum destes valores foi preenchido ou aprovado automaticamente. NWC pode ser negativo. Alterações de margem/CapEx devem refletir competição, capacidade, maturação e intensidade de investimento, e não extrapolar ganhos de títulos.

Terminal:

```text
NOPAT6 = EBIT5 × (1+g) × (1−taxa operacional)
Reinvestimento terminal = NOPAT6 × g/ROIC
FCFF6 = NOPAT6 × (1−g/ROIC)
TV5 = FCFF6/(WACC terminal−g)
```

WACC terminal e ROIC devem exceder g; NOPAT terminal deve ser positivo. O reinvestimento financia o crescimento: não se usa crescimento perpétuo gratuito. O motor mostra a diferença entre FCFF6 e FCFF5 e o peso do terminal no EV, para detetar transições pouco plausíveis. Não modela automaticamente prejuízos fiscais/NOL; não reconhece um reembolso imediato sobre EBIT negativo. Uma utilização material de NOL exige extensão revista do modelo.

A grelha 3×3 aplica choques de diagnóstico de ±100 pontos base ao desconto e ±50 pontos base a g. São stresses definidos para revisão, **não previsões nem intervalos estatísticos**. Combinações economicamente inválidas mostram erro e valor nulo. Os valores dos três cenários devem ordenar pessimista ≤ base ≤ otimista; o código rejeita pressupostos incoerentes em vez de os reordenar ou corrigir silenciosamente.

## Aprovações pendentes, separadas da metodologia aprovada

| Decisão/dado pendente | Fundamentação necessária |
| --- | --- |
| D&A operacional completo e juros pagos em OCF | Completar extração/mapeamento de âmbito; juros contabilísticos e depreciação PPE isolada não bastam |
| SBC económico e diluição | Definir custo sustentável e garantir que awards/capitalização/proventos não são duplicados |
| Taxas operacionais e benefícios fiscais da dívida/locações | Separar imposto sobre operações de ganhos de investimentos e restrições reais de dedutibilidade |
| CapEx sustentável, accrued PPE, finance leases e intangíveis | Ponte de investimento económico e crescimento; não classificar todo o CapEx de IA como extraordinário |
| NWC e ajustes EBIT/OCF | Identificar rubricas, sinais, reversões e recorrência; reconciliar rotas sem plug |
| Rf, ERP, beta, Kn, Kl e Kp | Fontes de mercado datadas, modelo de risco e custo marginal, não cupões históricos |
| Classes B e datas das cotações | Aprovar proxy para B e preços A/C comparáveis no mesmo dia; o snapshot recolhido tem dias diferentes |
| Preferenciais/capped calls, minoritários e outros ativos/claims | Valor integral de mercado, termos de conversão, tributação e ausência de dupla contagem |
| Pesos/betas anuais, margens, CapEx, g e ROIC terminal por cenário | Justificação económica para cada trajetória e a transição após conversão |
| Publicação/desbloqueio | Aprovação independente após revisão e testes; não é efetuada pelo motor |

## Execução, isolamento e manutenção

```sh
python -m unittest discover -s tests -v
python -m src.fcff_report --inputs data/fcff_inputs.json --output work/fcff_report.json
python -m scripts.prepare_fcff --annual-html work/annual.html --quarter-html work/quarter.html --fetch-quotes
```

Preparação lê originais locais, gera inputs ainda não aprovados e evidência em `work/fcff/`; a opção de cotações usa a fonte gratuita já existente. Não lê Secrets nem faz chamadas Telegram. O CLI de avaliação rejeita outputs em docs, src ou data para não sobrescrever o estado publicado. Os documentos HTML completos não ficam no repositório; URLs e hashes permitem reconstrução com os mesmos ficheiros. A extração não é um parser iXBRL universal: formatos/conceitos não suportados bloqueiam ou ficam em falta.

`data/fcff_inputs.json` e `data/fcff_sec_evidence.json` são artefactos de investigação; a monitorização não os importa. Nenhum código do workflow ou monitor em produção foi alterado para esta implementação. O relatório distingue `calculation_ready` (todos os inputs do cálculo revistos) de `valuation_ready` (continua sempre false nesta fase). Mesmo com dados sintéticos integralmente aprovados nos testes, `fair_value` publicado permanece nulo e `signal=NO_SIGNAL`. Resultados internos, quando possíveis, ficam apenas em `review_calculations`, fora do Pages e dos alertas.

O mapeamento de dados desta revisão está deliberadamente vinculado ao TTM setembro/2026. Novo período/entrega requer atualizar e rever o mapeamento, reconstruir componentes e reaprovar inputs; não existe atualização silenciosa de pressupostos. As cotações/rates expiram e devem ser recolhidas novamente na data de avaliação. A integração futura do novo modelo no dashboard e qualquer desbloqueio exigem uma alteração e revisão próprias. A monitorização atual mantém-se operacional durante este trabalho.
