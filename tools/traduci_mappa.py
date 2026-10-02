"""Le spiegazioni della macchina in inglese, per la mappa pubblica (30/09/2026). Le proposte di DeepSeek (proposizione,
   motivo dei principi, nota sul tipo, prove del seguito scritte dalla macchina) sono in italiano: qui DeepSeek le
   traduce, venti per chiamata, senza cambiarne il senso. Il testo dell'atto (frasi copiate alla lettera) NON si traduce.
     prepara  Mac  -> pubblicazione/mappa/da_tradurre.jsonl
     traduci  GPU  -> pubblicazione/mappa/tradotte.jsonl
"""
import argparse, concurrent.futures as cf, json, pathlib, re, threading, time
QUI = pathlib.Path(__file__).resolve().parent.parent
M = QUI/'pubblicazione'/'mappa'

def pulisci(t):
    t = ' '.join(str(t or '').split())
    t = re.sub(r'^DeepSeek, due letture: [^.]*\.\s*Motivo:\s*', '', t)
    return t

def prepara():
    D = json.load(open(M/'dati_ricchi.json', encoding='utf-8'))
    testi = set()
    for c in D['citazioni']:
        s = c.get('spiega') or {}
        for k in ('proposizione_it', 'motivo_principi_it', 'nota_tipo_it', 'altro_it'):
            if s.get(k): testi.add(pulisci(s[k]))
        for e in s.get('seguito') or []:
            if e.get('prova') and not e.get('testuale'): testi.add(pulisci(e['prova']))
    # solo i testi non ancora tradotti (01/10/2026: le proposte ricaricate hanno spiegazioni nuove); id dopo gli ultimi
    fatte, base = set(), 0
    if (M/'tradotte.jsonl').exists():
        for l in open(M/'tradotte.jsonl', encoding='utf-8'):
            x = json.loads(l); base = max(base, x['id'] + 1); fatte |= {a for a, _ in x['coppie']}
    testi = sorted(t for t in testi if t and t not in fatte)
    with open(M/'da_tradurre.jsonl', 'w', encoding='utf-8') as f:
        for i in range(0, len(testi), 20):
            f.write(json.dumps({'id': base + i // 20, 'testi': testi[i:i+20]}, ensure_ascii=False) + '\n')
    print(len(testi), 'testi in', (len(testi) + 19) // 20, 'blocchi')

MODULO = """Translate each Italian text below into clear, plain English for a public website about climate litigation.
Keep legal terms precise (e.g. "duty of care", "positive obligations under Articles 2 and 8 ECHR", "margin of appreciation"), keep case names, article numbers and quotations exactly, do not add or remove content, do not comment.
Return ONLY a JSON array of strings, same order and same number of items as the input ({n} items).

INPUT:
{testi}"""

def traduci(a):
    from openai import OpenAI
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=900)
    blocchi = [json.loads(l) for l in open(M/'da_tradurre.jsonl', encoding='utf-8')]
    uscita = M/'tradotte.jsonl'
    fatti = {json.loads(l)['id'] for l in open(uscita, encoding='utf-8')} if uscita.exists() else set()
    da_fare = [b for b in blocchi if b['id'] not in fatti]
    print(len(blocchi), 'blocchi,', len(da_fare), 'da fare', flush=True)
    def una(b):
        t = MODULO.format(n=len(b['testi']), testi=json.dumps(b['testi'], ensure_ascii=False, indent=0))
        for k in range(4):
            try:
                x = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': t}], max_tokens=6000,
                                                extra_body={'chat_template_kwargs': {'thinking': False}})
                s = x.choices[0].message.content or ''
                s = s[s.find('['): s.rfind(']') + 1]
                out = json.loads(s)
                if isinstance(out, list) and len(out) == len(b['testi']):
                    return {'id': b['id'], 'coppie': list(zip(b['testi'], [str(o) for o in out]))}
            except Exception:
                time.sleep(3 * (k + 1))
        return {'id': b['id'], 'coppie': [], 'errore': True}
    blocco = threading.Lock(); t0 = time.time()
    with cf.ThreadPoolExecutor(a.paralleli) as ex, open(uscita, 'a', encoding='utf-8') as f:
        for n, e in enumerate(ex.map(una, da_fare), 1):
            if e.get('errore'): continue
            with blocco: f.write(json.dumps(e, ensure_ascii=False) + '\n'); f.flush()
            if n % 50 == 0: print(f'  {n}/{len(da_fare)} [{time.time()-t0:.0f}s]', flush=True)
    print(f'fatto in {time.time()-t0:.0f}s', flush=True)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'traduci'])
    ap.add_argument('--paralleli', type=int, default=48); ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1'); ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    a = ap.parse_args()
    prepara() if a.fase == 'prepara' else traduci(a)
