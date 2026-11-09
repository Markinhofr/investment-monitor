import os,json,datetime,urllib.request,html,pathlib,sys
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parents[1]
TZ=ZoneInfo('Europe/Lisbon')
WATCH={'GOOGL':'Alphabet','SPGI':'S&P Global','V':'Visa','SU.PA':'Schneider Electric','ROG.SW':'Roche'}
def schedule(now):
 local=now.astimezone(TZ)
 return 'daily' if local.hour==22 and local.minute>=30 and local.minute<60 else ('weekly' if local.weekday()==6 and local.hour==10 and local.minute>=30 else None)
def quote(symbol):
 # Yahoo public chart endpoint is unofficial and may rate-limit; failures are explicit.
 url='https://query1.finance.yahoo.com/v8/finance/chart/'+symbol+'?range=5d&interval=1d'
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 InvestmentResearch/1.0'})
 with urllib.request.urlopen(req,timeout=15) as r: payload=json.load(r)
 obj=payload['chart']['result'][0]; meta=obj['meta']; stamps=obj.get('timestamp') or []
 closes=obj['indicators']['quote'][0]['close']; pairs=[(t,p) for t,p in zip(stamps,closes) if p is not None]
 if not pairs: raise ValueError('No closing prices')
 ts,price=pairs[-1]
 return {'price':round(price,4),'currency':meta.get('currency'),'as_of':datetime.datetime.fromtimestamp(ts,datetime.timezone.utc).isoformat(),'source':url,'type':'delayed_or_last_close'}
def load_json(path,default):
 return json.loads(path.read_text()) if path.exists() else default
def assess(q,fv):
 if not q: return {'label':'DADOS INSUFICIENTES','discount_pct':None}
 if not fv or not isinstance(fv.get('value'),(int,float)) or fv['value']<=0 or fv.get('currency')!=q['currency'] or not fv.get('source_url') or not fv.get('as_of'):
  return {'label':'SEM FAIR VALUE VERIFICADO','discount_pct':None}
 d=(fv['value']-q['price'])/fv['value']*100
 label='INVESTIGAR COMPRA' if d>=25 else 'ESTUDAR ENTRADA' if d>=15 else 'ACOMPANHAR' if d>=0 else 'REVER VALORIZAÇÃO'
 return {'label':label,'discount_pct':round(d,1)}
def claude_commentary(report):
 key=os.getenv('ANTHROPIC_API_KEY')
 if not key: return 'Claude API não configurada; análise baseada apenas em regras.'
 facts={'mode':report['mode'],'generated_at':report['generated_at'],'positions':[{'symbol':x['symbol'],'owned':x['owned'],'quote':x['quote'],'fair_value':x['fair_value'],'assessment':x['assessment'],'error':x['error']} for x in report['positions']]}
 body={'model':os.getenv('CLAUDE_MODEL','claude-sonnet-4-5'),'max_tokens':650,'system':'És um analista de investimentos cauteloso. Responde em português de Portugal. Usa apenas os dados JSON fornecidos; não inventes notícias, earnings, fundamentos ou preços justos. Sem fontes verificadas, declara dados insuficientes. Não executes ordens. Máximo 180 palavras.','messages':[{'role':'user','content':'Produz resumo de risco e prioridades com estes dados: '+json.dumps(facts)}]}
 req=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(body).encode(),headers={'x-api-key':key,'anthropic-version':'2023-06-01','content-type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=40) as r: result=json.load(r)
  return '\n'.join(b['text'] for b in result.get('content',[]) if b.get('type')=='text') or 'Sem comentário gerado.'
 except Exception as e:return 'Claude indisponível: '+type(e).__name__
def telegram(message):
 token=os.getenv('TELEGRAM_BOT_TOKEN'); chat=os.getenv('TELEGRAM_CHAT_ID')
 if not (token and chat): return 'not_configured'
 data=json.dumps({'chat_id':chat,'text':message[:3800]}).encode()
 req=urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',data=data,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as r: return 'sent' if json.load(r).get('ok') else 'failed'
def build(mode,offline=False):
 now=datetime.datetime.now(datetime.timezone.utc); portfolio=load_json(ROOT/'data/portfolio.json',{'positions':[]}); values=load_json(ROOT/'data/fair_values.json',{})
 rows=[]
 for pos in portfolio['positions']:
  sym=pos['symbol']; q=None; error=None
  if sym.endswith('_UNVERIFIED') or pos.get('exchange_symbol_unverified'): error='Ticker por confirmar'
  elif offline: error='Modo de teste sem dados externos'
  else:
   try: q=quote(sym)
   except Exception as e: error='Falha na fonte de preços: '+type(e).__name__
  fv=values.get(sym)
  a=assess(q,fv)
  rows.append({'symbol':sym,'name':pos['name'],'owned':pos['owned'],'quantity':pos.get('quantity'),'quote':q,'fair_value':fv,'assessment':a,'error':error})
 report={'generated_at':now.isoformat(),'timezone':'Europe/Lisbon','mode':mode,'note':'Research only; no trading. Fair values require verified manually sourced estimates. No AI API call is made. News/earnings are not monitored in this version.','positions':rows}
 report['claude_commentary']=claude_commentary(report) if not offline else 'Modo de teste: sem chamada à API.'
 docs=ROOT/'docs'; docs.mkdir(exist_ok=True)
 (docs/'latest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 cards=[]
 for r in rows:
  q=r['quote']; a=r['assessment']; fv=r['fair_value']; name=html.escape(r['name']); status='Carteira' if r['owned'] else 'Watchlist'
  price=f"{q['price']:.2f} {html.escape(q.get('currency') or '')}" if q else 'Indisponível'
  fair=f"{fv['value']} {html.escape(fv['currency'])}" if fv and isinstance(fv.get('value'),(int,float)) else 'Não verificado'
  disc=f"{a['discount_pct']:+.1f}%" if a['discount_pct'] is not None else '—'
  source=f"<a href='{html.escape(q['source'],quote=True)}' target='_blank' rel='noopener'>Fonte do preço</a> · {html.escape(q['as_of'])}" if q else html.escape(r['error'] or 'Sem cotação')
  cards.append(f"<article><div class='top'><h2>{name}</h2><span>{status}</span></div><p class='ticker'>{html.escape(r['symbol'])}</p><div class='metrics'><div><small>Último preço</small><strong>{price}</strong></div><div><small>Fair value</small><strong>{fair}</strong></div><div><small>Margem</small><strong>{disc}</strong></div></div><p class='status'>{html.escape(a['label'])}</p><p class='source'>{source}</p></article>")
 page='''<!doctype html><html lang="pt"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="1800"><title>Personal Investment Analyst</title><style>body{font:16px system-ui;background:#0c1423;color:#eaf1fc;margin:0;padding:32px;max-width:1100px;margin:auto}h1{font-size:2rem}p{line-height:1.5;color:#aab8cd}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:16px}article{background:#162238;border:1px solid #293c59;border-radius:16px;padding:20px}.top{display:flex;justify-content:space-between;gap:8px;align-items:center}.top h2{font-size:1.1rem;margin:0}.top span,.status{color:#82b7f9}.ticker{margin:6px 0 18px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.metrics small{display:block;color:#aab8cd;font-size:11px}.metrics strong{font-size:14px;overflow-wrap:anywhere}.source{font-size:11px;overflow-wrap:anywhere}a{color:#9ac7ff}.warning{background:#283347;padding:14px;border-radius:12px}</style><h1>Personal Investment Analyst</h1>'''
 page+=f"<p>Última execução: {html.escape(now.astimezone(TZ).strftime('%Y-%m-%d %H:%M %Z'))} · {html.escape(mode)}</p><p class='warning'>⚠️ Preços atrasados/último fecho; dados não garantidos. Sem fair values verificados não há sinais de compra. Posições e quantidades por confirmar. Este site é público: não colocar dados pessoais, valores investidos ou segredos neste repositório.</p><div class='grid'>"+''.join(cards)+"</div><h2>Comentário Claude (opcional)</h2><p>"+html.escape(report['claude_commentary'])+"</p><p>Dados estruturados: <a href='latest.json'>latest.json</a>. Não são executadas ordens. Alertas de notícias e earnings ainda não implementados.</p></html>"
 (docs/'index.html').write_text(page)
 return report
def main():
 mode=os.getenv('REPORT_MODE','auto'); now=datetime.datetime.now(datetime.timezone.utc)
 if mode=='auto': mode=schedule(now)
 if mode is None:
  print('Not scheduled for Lisbon local time'); return
 report=build(mode,os.getenv('OFFLINE_TEST')=='1')
 signals=[r for r in report['positions'] if r['assessment']['label'] in ('INVESTIGAR COMPRA','ESTUDAR ENTRADA')]
 msg=f"📈 Investment Analyst — {mode} — {now.astimezone(TZ):%d/%m %H:%M} Lisboa\n"+('\n'.join(f"{r['symbol']}: {r['assessment']['label']} ({r['assessment']['discount_pct']}%)" for r in signals) if signals else 'Sem sinais de valorização verificáveis. Consultar dashboard.')
 print(msg); print('Telegram:',telegram(msg))
if __name__=='__main__':main()
