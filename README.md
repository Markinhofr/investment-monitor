# Personal Investment Analyst — Cloud v1.1

**Status:** pacote pronto a configurar, **não instalado nem agendado na tua conta**. Não coloca ordens de bolsa. O GitHub Actions funciona com o teu computador desligado. O Claude é **opcional via API Anthropic, faturada à parte**; a subscrição Claude Pro não inclui créditos API. O dashboard é estático e público no GitHub Pages. Sem API, os relatórios e alertas de valorização são calculados por regras, sem interpretação de IA.

## Arquitetura

GitHub Actions (cron a cada hora, minuto 30 UTC) → valida hora de `Europe/Lisbon` → Yahoo Finance Chart (cotações indicativas, fonte **não oficial**, pode falhar) → `data/fair_values.json` (fair values **introduzidos manualmente, com fonte**) → avaliação determinística → Claude API opcional → `docs/index.html` e `docs/latest.json` → GitHub Pages + Telegram Bot API.

A rotina diária é às **22:30 hora de Lisboa**. A semanal é **domingo 10:30 hora de Lisboa**. Mudanças de horário verão/inverno são tratadas com `zoneinfo`. **GitHub Actions pode atrasar ou falhar**; não há garantia de execução ao minuto. O workflow corre a cada hora, mas só atualiza na janela definida, ou quando executado manualmente. GitHub pode desativar cron em repositórios públicos inativos.

## Instalação (aprox. 20–40 minutos)

1. Cria uma conta em https://github.com e um repositório **novo, público**, por exemplo `investment-monitor`. Extrai este ZIP e carrega **o conteúdo da pasta** para a raiz do repositório, incluindo `.github/workflows/monitor.yml` (pastas ocultas). Não publiques dados pessoais ou quantidades de investimento: o dashboard é público. Para dashboard privado, será necessária outra arquitetura de hosting/autenticação.
2. Em **Settings → Actions → General → Workflow permissions**, seleciona **Read and write permissions**. Ativa Actions se necessário.
3. Em **Settings → Pages → Build and deployment**, escolhe **Deploy from a branch**, branch `main`, pasta `/docs`, e guarda. Após a primeira execução, abre `https://TEU-UTILIZADOR.github.io/investment-monitor/` (substitui os nomes). Alguns minutos de propagação são normais.
4. No Telegram, conversa com **@BotFather**, usa `/newbot` e guarda o token **privadamente**. Envia `/start` ao bot criado. Para obter o teu chat ID, abre no teu browser `https://api.telegram.org/bot<TOKEN>/getUpdates` após enviares uma mensagem ao bot e procura `message.chat.id`. **Não partilhes o token nem o coloques no repositório.**
5. No GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Cria `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` com os valores acima. Opcional: `ANTHROPIC_API_KEY` obtida na Anthropic Console, com faturação e limites configurados; o modelo padrão `claude-sonnet-4-5` poderá necessitar de atualização para um identificador suportado na tua conta. Se não definires a chave, o sistema continua sem IA.
6. Vai a **Actions → Investment monitoring → Run workflow**, escolhe `daily`. Aguarda a execução, abre os logs e confirma `Telegram: sent`. Verifica o dashboard Pages e o ficheiro `docs/latest.json`.
7. Abre `data/portfolio.json`: confirma os **tickers corretos da bolsa onde negoceias** (VWCE é apenas hipótese; os outros dois ETFs estão propositadamente `UNVERIFIED`). Não coloques quantidades nem custos se não quiseres tornar essa informação pública. A watchlist das cinco ações **não é carteira detida**.
8. Para ativar alertas de fair value, edita `data/fair_values.json`, seguindo o exemplo abaixo, com **estimativa verificada, mesma moeda do ticker, data e URL da fonte**. Não uses fair values antigos sem rever os pressupostos.
9. Espera pela execução das 22:30 de Lisboa e verifica o histórico em Actions. No domingo às 10:30 é gerado o relatório semanal (nesta v1 o semanal usa o mesmo conjunto de métricas e comentário, não inclui comparação histórica profunda).

## Exemplo de fair value (fictício — NÃO copiar como dado real)

```json
{
  "GOOGL": {
    "value": 100.0,
    "currency": "USD",
    "as_of": "2026-11-09",
    "source_url": "https://example.org/valuation",
    "method": "DCF hipotético"
  }
}
```

## Testes

Local: `python -m unittest discover -s tests -v` (8 testes); `OFFLINE_TEST=1 REPORT_MODE=daily python src/monitor.py`. Depois abre `docs/index.html`. O modo offline não contacta Yahoo nem Claude; Telegram só é enviado se existirem as duas variáveis de ambiente.

Na cloud: **Actions → Run workflow → daily**, verificar execução, mensagem Telegram, data de atualização no dashboard e `latest.json`. Para verificar horário de verão: os testes cobrem Lisboa no inverno e no verão.

## Custos

GitHub Actions e Pages podem caber no escalão gratuito, sujeitos a políticas e limites atuais. Telegram Bot API não cobra por este uso típico. Yahoo Chart não é uma fonte com SLA nem licença de dados profissionais. **Anthropic API é paga por utilização**, separada do Claude Pro; coloca um limite de faturação e acompanha o consumo. O objetivo de **até 10 €/mês adicionais** é plausível para esta versão com uso reduzido, **não garantido**. Sem API, não há custo de IA, mas também não há comentário Claude.

## Limitações honestas

- Não existe integração direta com a tua corretora, nem cálculo de P&L com quantidades desconhecidas.
- Não há recolha automática de demonstrações financeiras, earnings, notícias, revisões de analistas, fair value nem monitorização intradiária nesta v1. Esses módulos precisam de APIs/licenças adicionais.
- As cotações podem estar atrasadas, indisponíveis, ou ter símbolo/moeda diferentes dos teus ETFs; nunca interpretar dados em falta como zero.
- Um desconto ao fair value é um **sinal para investigar**, não uma ordem de compra. Não se vende só por uma queda no preço.
- O dashboard em GitHub Pages é público; não coloques chaves, informação pessoal ou valores privados nos ficheiros.
- A rotina semanal não substitui análise fundamental trimestral. O relatório Claude opcional está limitado aos dados estruturados recolhidos.

## Evolução v2

Adicionar API licenciada de fundamentos/earnings/notícias, histórico de sinais, armazenamento privado e dashboard com autenticação, e regras de qualidade dos dados (data da fonte, validade, reconciliação de moedas, verificação de anúncios). Só depois produzir recomendações com fundamentos realmente atualizados.
