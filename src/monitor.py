
import os
import math
import hashlib
import json
import datetime
import urllib.request
import html
import pathlib
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Europe/Lisbon")

WATCH = {
    "GOOGL": "Alphabet",
    "SPGI": "S&P Global",
    "V": "Visa",
    "SU.PA": "Schneider Electric",
    "ROG.SW": "Roche",
}


def schedule(now):
    local = now.astimezone(TZ)
    if local.hour == 22 and 30 <= local.minute < 60:
        return "daily"
    if local.weekday() == 6 and local.hour == 10 and local.minute >= 30:
        return "weekly"
    return None


def quote(symbol):
    # Endpoint público não oficial: pode falhar ou limitar pedidos.
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + symbol
        + "?range=5d&interval=1d"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 InvestmentResearch/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        payload = json.load(response)

    obj = payload["chart"]["result"][0]
    meta = obj["meta"]
    stamps = obj.get("timestamp") or []
    closes = obj["indicators"]["quote"][0]["close"]
    pairs = [
        (timestamp, price)
        for timestamp, price in zip(stamps, closes)
        if price is not None
    ]

    if not pairs:
        raise ValueError("No closing prices")

    timestamp, price = pairs[-1]
    if not math.isfinite(price) or price <= 0 or not meta.get('currency'):
        raise ValueError('Invalid quote')
    return {
        "price": round(price, 4),
        "currency": meta.get("currency"),
        "as_of": datetime.datetime.fromtimestamp(
            timestamp, datetime.timezone.utc
        ).isoformat(),
        "source": url,
        "type": "delayed_or_last_close",
    }


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def valid_fair_value(fv):
    from src.research import number, recent
    today = datetime.datetime.now(datetime.timezone.utc).date()
    return bool(isinstance(fv, dict) and fv.get('verified') is True
                and fv.get('valuation_ready') is True and number(fv.get('value'), True)
                and recent(fv.get('as_of'), today, 120) and fv.get('source_url'))


def assess(q, fv):
    from src.research import number, recent
    if not q or not number(q.get('price'), True) or not recent(
            q.get('as_of'), datetime.datetime.now(datetime.timezone.utc).date(), 5):
        return {'label': 'DADOS INSUFICIENTES', 'discount_pct': None}
    if not valid_fair_value(fv) or fv.get('currency') != q.get('currency'):
        return {'label': 'SEM FAIR VALUE VERIFICADO', 'discount_pct': None}
    discount = (fv['value'] - q['price']) / fv['value'] * 100
    label = ('INVESTIGAR COMPRA' if discount >= 25 else 'ESTUDAR ENTRADA' if discount >= 15
             else 'ACOMPANHAR' if discount >= 0 else 'REVER VALORIZAÇÃO')
    return {'label': label, 'discount_pct': round(discount, 1)}


def claude_commentary(report):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return "Claude API não configurada; análise baseada apenas em regras."

    facts = {
        "mode": report["mode"],
        "generated_at": report["generated_at"],
        "positions": [
            {
                "symbol": item["symbol"],
                "owned": item["owned"],
                "quote": item["quote"],
                "fair_value": item["fair_value"],
                "assessment": item["assessment"],
                "error": item["error"],
            }
            for item in report["positions"]
        ],
    }

    body = {
        "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
        "max_tokens": 650,
        "system": (
            "És um analista de investimentos cauteloso. "
            "Responde em português de Portugal. "
            "Usa apenas os dados JSON fornecidos; não inventes "
            "notícias, earnings, fundamentos ou preços justos. "
            "Sem fontes verificadas, declara dados insuficientes. "
            "Não executes ordens. Máximo 180 palavras."
        ),
        "messages": [
            {
                "role": "user",
                "content": (
                    "Produz resumo de risco e prioridades com estes dados: "
                    + json.dumps(facts)
                ),
            }
        ],
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            result = json.load(response)
        return "\n".join(
            block["text"]
            for block in result.get("content", [])
            if block.get("type") == "text"
        ) or "Sem comentário gerado."
    except Exception as error:
        return "Claude indisponível: " + type(error).__name__


def telegram(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")

    if not (token and chat):
        return "not_configured"

    data = json.dumps({
        "chat_id": chat,
        "text": message[:3800],
    }).encode()

    req = urllib.request.Request(
        "https://api.telegram.org/bot" + token + "/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        return "sent" if json.load(response).get("ok") else "failed"


def build(mode, offline=False, research=None):
    now = datetime.datetime.now(datetime.timezone.utc)

    portfolio = load_json(
        ROOT / "data/portfolio.json",
        {"positions": []},
    )
    values = load_json(ROOT / "data/fair_values.json", {})

    if research is None:
        from src.dcf_report import generate_report
        research = generate_report(offline)
    # Alphabet must always use this run's validated DCF, never an older manual value.
    values.pop('GOOGL', None)
    if research['valuation_ready']:
        values['GOOGL'] = {'value': research['scenarios']['base']['fair_value'],
                           'currency': 'USD', 'source_url': research['source'],
                           'as_of': research['period_end'], 'verified': True, 'valuation_ready': True}
    rows = []

    for pos in portfolio["positions"]:
        symbol = pos["symbol"]
        q = None
        error = None

        if symbol.endswith("_UNVERIFIED") or pos.get(
            "exchange_symbol_unverified"
        ):
            error = "Ticker por confirmar"
        elif offline:
            error = "Modo de teste sem dados externos"
        else:
            try:
                q = quote(symbol)
            except Exception as exc:
                error = (
                    "Falha na fonte de preços: "
                    + type(exc).__name__
                )

        candidate = values.get(symbol)
        fv = candidate if valid_fair_value(candidate) else None
        assessment = assess(q, fv)

        rows.append({
            "symbol": symbol,
            "name": pos["name"],
            "owned": pos["owned"],
            "quantity": pos.get("quantity"),
            "quote": q,
            "fair_value": fv,
            "assessment": assessment,
            "error": error,
        })

    alphabet_quote = next((x['quote'] for x in rows if x['symbol'] == 'GOOGL'), None)
    for scenario in research['scenarios'].values():
        scenario['margin_of_safety_pct'] = assess(alphabet_quote, {
            'value': scenario['fair_value'], 'currency': 'USD', 'source_url': research['source'],
            'as_of': research['period_end'], 'verified': research['verified'],
            'valuation_ready': research['valuation_ready']})['discount_pct']
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'docs/dcf_alphabet.json').write_text(json.dumps(research, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {
        "generated_at": now.isoformat(),
        "timezone": "Europe/Lisbon",
        "mode": mode,
        "note": (
            "Research only; no trading. Fair values require validated inputs. "
            "Alphabet SEC filings monitored; valuation blocked until validated."
        ),
        "positions": rows,
        "alphabet": research,
        "update_status": research["data_status"],
    }

    report["claude_commentary"] = (
        claude_commentary(report)
        if not offline and os.getenv("ENABLE_PAID_COMMENTARY") == "1"
        else "Comentário pago desativado; análise determinística."
    )

    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)

    history = load_json(docs / 'history.json', [])
    snapshot = {'generated_at': report['generated_at'], 'status': research['data_status'],
                'positions': [{'symbol': x['symbol'], 'quote': x['quote'],
                               'assessment': x['assessment'], 'fair_value': x['fair_value']} for x in rows]}
    history = (history + [snapshot])[-366:]
    (docs / 'history.json').write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')
    (docs / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cards = []

    for item in rows:
        q = item["quote"]
        assessment = item["assessment"]
        fv = item["fair_value"]
        name = html.escape(item["name"])
        status = "Carteira" if item["owned"] else "Watchlist"

        price = (
            f"{q['price']:.2f} "
            f"{html.escape(q.get('currency') or '')}"
            if q else "Indisponível"
        )

        fair = (
            f"{fv['value']} {html.escape(fv['currency'])}"
            if fv and isinstance(fv.get("value"), (int, float))
            else "Não verificado"
        )

        discount = (
            f"{assessment['discount_pct']:+.1f}%"
            if assessment["discount_pct"] is not None
            else "—"
        )

        source = (
            f"<a href='{html.escape(q['source'], quote=True)}' "
            f"target='_blank' rel='noopener'>Fonte do preço</a> · "
            f"{html.escape(q['as_of'])}"
            if q
            else html.escape(item["error"] or "Sem cotação")
        )

        cards.append(
            f"<article>"
            f"<div class='top'><h2>{name}</h2>"
            f"<span>{status}</span></div>"
            f"<p class='ticker'>{html.escape(item['symbol'])}</p>"
            f"<div class='metrics'>"
            f"<div><small>Último preço</small><strong>{price}</strong></div>"
            f"<div><small>Fair value</small><strong>{fair}</strong></div>"
            f"<div><small>Margem</small><strong>{discount}</strong></div>"
            f"</div>"
            f"<p class='status'>{html.escape(assessment['label'])}</p>"
            f"<p class='source'>{source}</p>"
            f"</article>"
        )

    page = """<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="1800">
<title>Personal Investment Analyst</title>
<style>
body {
    font: 16px system-ui;
    background: #0c1423;
    color: #eaf1fc;
    margin: 0 auto;
    padding: 32px;
    max-width: 1100px;
}
h1 { font-size: 2rem; }
p { line-height: 1.5; color: #aab8cd; }
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(285px, 1fr));
    gap: 16px;
}
article {
    background: #162238;
    border: 1px solid #293c59;
    border-radius: 16px;
    padding: 20px;
}
.top {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    align-items: center;
}
.top h2 { font-size: 1.1rem; margin: 0; }
.top span, .status { color: #82b7f9; }
.ticker { margin: 6px 0 18px; }
.metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
}
.metrics small {
    display: block;
    color: #aab8cd;
    font-size: 11px;
}
.metrics strong {
    font-size: 14px;
    overflow-wrap: anywhere;
}
.source {
    font-size: 11px;
    overflow-wrap: anywhere;
}
a { color: #9ac7ff; }
.warning {
    background: #283347;
    padding: 14px;
    border-radius: 12px;
}
.dcf-button {
    display: inline-block;
    background: #2563eb;
    color: white;
    padding: 14px 18px;
    border-radius: 8px;
    text-decoration: none;
    margin-top: 20px;
}
</style>
</head>
<body>
<h1>Personal Investment Analyst</h1>
"""

    local_time = html.escape(
        now.astimezone(TZ).strftime("%Y-%m-%d %H:%M %Z")
    )

    page += (
        f"<p>Última execução: {local_time} · "
        f"{html.escape(mode)}</p>"
        "<p class='warning'>⚠️ Preços atrasados/último fecho; "
        "dados não garantidos. Sem fair values verificados não há "
        "sinais de compra. Posições e quantidades por confirmar. "
        "Este site é público: não colocar dados pessoais, valores "
        "investidos ou segredos neste repositório.</p>"
        "<div class='grid'>"
        + "".join(cards)
        + "</div>"
        "<h2>Comentário Claude (opcional)</h2>"
        "<p>"
        + html.escape(report["claude_commentary"])
        + "</p>"
        "<p>Dados estruturados: "
        "<a href='latest.json'>latest.json</a>. "
        "Não são executadas ordens. Novos resultados da Alphabet são detetados via SEC.</p>"
    )

    page += '<h2>Alphabet — métricas financeiras validadas</h2>'
    for key, item in research.get('metrics', {}).items():
        page += '<p>' + html.escape(key + ': ' + str(item['value']) + ' USD · ' + item['end']) + '</p>'
    page += '<p>FCF TTM: ' + html.escape(str(research['fcf_ttm']['value']) if research['fcf_ttm']['verified'] else 'Pendente de validação') + ' USD</p>'
    page += '<p>FCF normalizado: ' + html.escape(str(research['fcf_normalized']['value']) if research['valuation_ready'] else 'Pendente de revisão') + ' USD</p>'
    page += "<h2>Histórico das últimas atualizações</h2><ul>" + ''.join(
        '<li>' + html.escape(x['generated_at'] + ' · ' + x['status']) + '</li>' for x in history[-10:]) + "</ul><p><a href='history.json'>Histórico completo (JSON)</a></p>"
    page += "<p>Estado SEC/DCF: " + html.escape(research['data_status']) + "</p>"
    # Ligação permanente para a análise DCF da Alphabet.
    page += """
<div>
    <a class="dcf-button" href="dcf.html">
        Ver análise fundamental da Alphabet
    </a>
    <p>Modelo experimental — valores ainda não verificados.</p>
</div>
</body>
</html>
"""

    (docs / "index.html").write_text(page, encoding="utf-8")
    return report


DASHBOARD_URL = os.getenv(
    "DASHBOARD_URL",
    "https://markinhofr.github.io/investment-monitor/",
)


def notification_message(report, previous, mode, now):
    """Only notify for meaningful changes; send a weekly digest regardless."""
    previous_positions = {
        row.get("symbol"): row
        for row in (previous or {}).get("positions", [])
        if isinstance(row, dict) and row.get("symbol")
    }
    updates = []
    for row in report["positions"]:
        symbol = row["symbol"]
        old = previous_positions.get(symbol)
        current_quote = row.get("quote") or {}
        old_quote = (old or {}).get("quote") or {}
        price = current_quote.get("price")
        old_price = old_quote.get("price")
        current_status = (row.get("assessment") or {}).get("label")
        old_status = ((old or {}).get("assessment") or {}).get("label")

        if current_status != old_status and current_status in (
            "INVESTIGAR COMPRA", "ESTUDAR ENTRADA", "ACOMPANHAR",
            "REVER VALORIZAÇÃO",
        ):
            updates.append(f"🎯 {symbol}: novo estado — {current_status}")

        old_fv = (old or {}).get('fair_value') or {}
        current_fv = row.get('fair_value') or {}
        if old_fv.get('value', 0) > 0 and current_fv.get('value', 0) > 0:
            delta = (current_fv['value'] / old_fv['value'] - 1) * 100
            if abs(delta) >= 5:
                updates.append(f"DCF {symbol}: fair value base revisto {delta:+.1f}%")
        if (isinstance(price, (int, float)) and
                isinstance(old_price, (int, float)) and old_price > 0):
            change = (price / old_price - 1) * 100
            if abs(change) >= 3:
                updates.append(
                    f"{'📈' if change > 0 else '📉'} {symbol}: "
                    f"{price:.2f} {current_quote.get('currency') or ''} "
                    f"({change:+.1f}% desde a última execução)"
                )
        elif old and bool(current_quote) != bool(old_quote):
            updates.append(
                f"{'✅' if current_quote else '⚠️'} {symbol}: "
                f"{'cotação recuperada' if current_quote else 'cotação indisponível'}"
            )

    current_research = report.get('alphabet', {})
    old_research = (previous or {}).get('alphabet', {})
    if current_research.get('accession') and current_research.get('accession') != old_research.get('accession'):
        updates.append('📑 Alphabet: nova demonstração SEC — ' + str(current_research.get('period_end')))
    if current_research.get('data_status') != old_research.get('data_status'):
        updates.append('Validação Alphabet: ' + str(current_research.get('data_status')))
    # The first run and weekly runs provide a useful baseline/digest.
    if mode == "weekly" or previous is None:
        digest = []
        for row in report["positions"]:
            q = row.get("quote") or {}
            if isinstance(q.get("price"), (int, float)):
                digest.append(
                    f"• {row['symbol']}: {q['price']:.2f} "
                    f"{q.get('currency') or ''}"
                )
        if digest:
            updates.insert(0, "📊 Últimas cotações disponíveis:\n" + "\n".join(digest))
        elif previous is None:
            updates.append("⚠️ Ainda não existem cotações disponíveis.")

    if not updates:
        return None

    title = "Resumo semanal" if mode == "weekly" else "Atualização relevante"
    timestamp = now.astimezone(TZ).strftime("%d/%m/%Y %H:%M")
    return (
        f"📊 Investment Monitor — {title}\n"
        f"🕒 {timestamp} Lisboa\n\n"
        + "\n".join(updates)
        + "\n\n🔗 Dashboard: " + DASHBOARD_URL
        + "\n⚠️ Preços podem estar atrasados; sem fair value validado não há sinais de compra."
    )


def main():
    mode = os.getenv("REPORT_MODE", "auto")
    now = datetime.datetime.now(datetime.timezone.utc)

    if mode == "auto":
        mode = schedule(now)
    if mode is None:
        print("Not scheduled for Lisbon local time")
        return

    offline = os.getenv('OFFLINE_TEST') == '1'
    # Compare with the last successfully notified report, so delivery failures retry.
    state_path = ROOT / 'data/notification_state.json'
    state = load_json(state_path, {})
    previous = state.get('report')
    report = build(mode, offline)
    message = notification_message(report, previous, mode, now)
    week = now.astimezone(TZ).strftime('%G-%V')
    # Same weekly digest and same payload are suppressed on workflow reruns.
    if mode == 'weekly' and state.get('week') == week:
        message = notification_message(report, previous, 'daily', now)
    if not message:
        print('Telegram: sem alterações relevantes')
        return
    digest = hashlib.sha256(message.split('Lisboa', 1)[-1].encode()).hexdigest()
    if digest == state.get('digest') or offline:
        print('Telegram: suprimido (duplicado ou teste offline)')
        return
    try:
        status = telegram(message)
    except Exception as error:
        status = type(error).__name__
    print('Telegram:', status)
    if status == 'sent':
        state_path.write_text(json.dumps({'digest': digest, 'week': week if mode == 'weekly' else state.get('week'),
                                         'report': report}, ensure_ascii=False, indent=2), encoding='utf-8')
    elif status != 'not_configured':
        raise RuntimeError('Telegram delivery failed; state retained for retry')


if __name__ == "__main__":
    main()
