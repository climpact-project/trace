"""DEEPSEEK DALL'API — lo stesso terzo giro di `deepseek_giro3.py`, senza pod.

   PERCHE' (decisione del PI, 23/09/2026 sera). Un pod B300 costa circa 7 euro
   l'ora e ne spende una solo per prepararsi (scaricare 150 GB, compilare);
   due pod si sono fermati a meta' lavoro. L'API di DeepSeek fa pagare solo
   quello che legge e scrive: stimati 5-7 dollari fuori dalle ore di punta.

   ATTENZIONE, VA SCRITTO NEL PAPER. Dal 10/09/2026 l'API serve DeepSeek
   V4.1 Flash (nome `deepseek-flash`), non i pesi V4 Flash che gireranno sul
   Mac Studio. Questa prova dice se il fascicolo e il modulo di osservazioni
   funzionano; il numero definitivo va rimisurato in locale.

   STESSE DOMANDE, STESSO FORMATO DI USCITA di `deepseek_giro3.py`
   (`training/deepseek_api_v{v}_{parte}.json`), cosi' l'analisi e' una sola.
   Le cinque letture sono cinque chiamate: dalla seconda il prompt e' in cache
   e costa il 98% in meno.

   MISURATO PRIMA DI PARTIRE (23/09/2026). Con lo sforzo di ragionamento di
   serie l'API scrive 8.000 token a lettura e tronca la risposta; con `low`
   circa 3.300-4.000, con `minimal` circa 3.000. Si usa `low` e tre letture
   invece di cinque: v2 e v3 su 400 righe stimati 6-7 dollari.

   PROTEZIONI. Riprende da dove si e' fermato (`.jsonl` riga per riga); si
   ferma da solo se la spesa stimata supera `--tetto` dollari; non parte nelle
   ore di punta (01-04 e 06-10 UTC, lun-ven), quando il prezzo raddoppia. La
   chiave si legge da `~/sabin-corpus/.deepseek_key` e non si stampa mai.
"""
import argparse, concurrent.futures as cf, datetime, json, pathlib, sys, threading, time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
from giudica_llm import costruisci, estrai  # noqa: E402
from deepseek_giro3 import prompt_fascicolo  # noqa: E402

PREZZI = {'ingresso': 0.15, 'cache': 0.003, 'uscita': 0.60}   # dollari per milione, fuori punta


def in_punta(t=None):
    t = t or datetime.datetime.now(datetime.timezone.utc)
    return t.weekday() < 5 and (1 <= t.hour < 4 or 6 <= t.hour < 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--versioni', default='3,2')
    ap.add_argument('--parti', default='prova,addestramento')
    ap.add_argument('--letture', type=int, default=3)
    ap.add_argument('--sforzo', default='low', help='reasoning_effort: con il valore di serie l API ragiona fino a 8.000 token a lettura, cinque volte il modello locale')
    ap.add_argument('--paralleli', type=int, default=24)
    ap.add_argument('--tetto', type=float, default=8.0, help='dollari')
    ap.add_argument('--max-righe', type=int, default=0)
    ap.add_argument('--modello', default='deepseek-flash')
    # LOCALE (25/09/2026): lo stesso giro contro DeepSeek acceso su ReCaS (vLLM, 4 H100).
    # Stesse domande e stessa analisi; cambia solo dove si chiede e il nome dei file.
    ap.add_argument('--base-url', default='https://api.deepseek.com')
    ap.add_argument('--chiave-file', default=str(QUI/'.deepseek_key'))
    ap.add_argument('--prefisso', default='deepseek_api', help='nome dei file di uscita in training/')
    a = ap.parse_args()
    locale = a.base_url != 'https://api.deepseek.com'
    if in_punta() and not locale:
        sys.exit('ore di punta: il prezzo e\' doppio, riprovare dopo le 10 UTC (12 in Italia)')
    from openai import OpenAI
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    T = QUI/'training'
    fascicolo = (QUI/'cited-cases'/'urgenda-fascicolo.md').read_text(encoding='utf-8')
    spesa = {'dollari': 0.0, 'ingresso': 0, 'cache': 0, 'uscita': 0}
    blocco = threading.Lock()
    fermo = threading.Event()

    def chiama(testo):
        for tentativo in range(5):
            try:
                r = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': testo}],
                                                max_tokens=8000, extra_body=({'chat_template_kwargs': {'thinking': True, 'reasoning_effort': a.sforzo}} if locale
                                                            else {'thinking': {'type': 'enabled'}, 'reasoning_effort': a.sforzo}))
                u = r.usage
                hit = getattr(u, 'prompt_cache_hit_tokens', 0) or 0
                miss = (getattr(u, 'prompt_cache_miss_tokens', None) or (u.prompt_tokens - hit))
                with blocco:
                    spesa['ingresso'] += miss; spesa['cache'] += hit; spesa['uscita'] += u.completion_tokens
                    spesa['dollari'] += (miss*PREZZI['ingresso'] + hit*PREZZI['cache'] + u.completion_tokens*PREZZI['uscita'])/1e6
                    if spesa['dollari'] > a.tetto:
                        fermo.set()
                m = r.choices[0].message
                return {'testo': m.content or '', 'ragionamento': getattr(m, 'reasoning_content', '') or '',
                        'token': u.completion_tokens}
            except Exception as e:  # rete o limiti: si riprova con pausa crescente
                time.sleep(5 * (tentativo + 1)); ultimo = repr(e)[:200]
        return {'testo': '', 'errore': ultimo, 'token': 0}

    def una_riga(r, v):
        # v3 fascicolo; v4 fascicolo piu' le regole del PI su che cosa conta come ripresa
        testo = prompt_fascicolo(r, fascicolo, regole=(v == 4)) if v >= 3 else costruisci(r, v)
        # La maschera del nome serviva ad addestrare i modelli piccoli (§58); il lettore deve
        # leggere il testo come l'hanno letto i validatori. Nel primo giro sul pod (§61.5) il
        # testo era ancora mascherato: va detto quando si confrontano i numeri.
        testo = testo.replace('⟦CASO_CITATO⟧', 'Urgenda')
        letture = []
        for _ in range(a.letture):          # in sequenza: dalla seconda il prompt e' in cache
            if fermo.is_set():
                return None
            letture.append(chiama(testo))
        g = [estrai(x['testo']) for x in letture]
        return {'id': r['id'], 'etichetta': r['etichetta'], 'sonda_id': r.get('sonda_id'), 'case_id': r.get('case_id'),
                'letture': g, 'ragionamenti': [x['ragionamento'] for x in letture],
                'voti_ripresa': sum(x.get('esito') == 'RIPRESA' for x in g), 'token': [x['token'] for x in letture]}

    for parte in a.parti.split(','):
        righe = [json.loads(x) for x in open(T/f'urgenda_decisione_{parte}_corrette_larghe.jsonl', encoding='utf-8') if x.strip()]
        if a.max_righe:
            righe = righe[:a.max_righe]
        for v in [int(x) for x in a.versioni.split(',')]:
            parziale = T/f'{a.prefisso}_v{v}_{parte}.jsonl'
            fatte = {json.loads(l)['id'] for l in open(parziale, encoding='utf-8')} if parziale.exists() else set()
            da_fare = [r for r in righe if r['id'] not in fatte]
            print(f'v{v} {parte}: {len(fatte)} gia\' fatte, {len(da_fare)} da fare', flush=True)
            t0 = time.time()
            with cf.ThreadPoolExecutor(a.paralleli) as ex, open(parziale, 'a', encoding='utf-8') as f:
                for n, esito in enumerate(ex.map(lambda r: una_riga(r, v), da_fare), 1):
                    if esito is None:
                        continue
                    f.write(json.dumps(esito, ensure_ascii=False) + '\n'); f.flush()
                    if n % 20 == 0:
                        print(f'  {n}/{len(da_fare)}  spesa stimata {spesa["dollari"]:.2f} $  [{time.time()-t0:.0f}s]', flush=True)
            if fermo.is_set():
                sys.exit(f'FERMATO: spesa stimata {spesa["dollari"]:.2f} $ oltre il tetto di {a.tetto} $')
            tutte = [json.loads(l) for l in open(parziale, encoding='utf-8')]
            (T/f'{a.prefisso}_v{v}_{parte}.json').write_text(json.dumps(tutte, ensure_ascii=False, indent=1), encoding='utf-8')
            y = [x['etichetta'] for x in tutte]
            for soglia in (1, 2, 3, a.letture):
                p = [x['voti_ripresa'] >= soglia for x in tutte]
                tp = sum(u and q for u, q in zip(y, p)); P = sum(p)
                print(f'  v{v} {parte:13s} almeno {soglia}/{a.letture}: propone {P:3d}  precisione {tp/max(P,1):.0%}  trova {tp}/{sum(y)} = {tp/max(sum(y),1):.0%}', flush=True)
    print(f'spesa stimata totale {spesa["dollari"]:.2f} $ | token: ingresso {spesa["ingresso"]}, cache {spesa["cache"]}, uscita {spesa["uscita"]}')


if __name__ == '__main__':
    main()
