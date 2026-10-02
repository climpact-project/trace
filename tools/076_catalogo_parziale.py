"""IL CATALOGO PARZIALE — cercare per pagine porta piu' rumore? E il punto si perde?

   IL TIMORE DEL PI (23/09/2026). Una pagina contiene molti argomenti, quindi
   somiglia a molte domande: un indice per pagine potrebbe tirare su piu'
   rumore di uno per frammenti. E al validatore arriverebbe una pagina, non il
   punto. Le prove del §60.2 non rispondono: misurano come un modello ORDINA
   righe gia' trovate, non che cosa trova cercando in un corpus.

   LA PROVA. Un corpus in piccolo: i 217 documenti con righe semantiche
   giudicate, piu' 300 documenti mai giudicati presi a caso come disturbo.
   Due indici sugli stessi documenti — a frammenti (come `007_build_chunks.py`) e
   a pagine — con piu' modelli. Per ogni sonda si cerca in tutto il catalogo
   e si guarda che cosa sta ai primi posti:
     trovate     quante pagine con una ripresa vera (righe di PROVA) ci sono;
     bocciate    quante pagine gia' bocciate dai validatori per quella sonda;
     disturbo    quanta parte dei primi posti viene dai documenti mai giudicati;
     puntamento  (solo indice a pagine) se, dentro una pagina vera trovata, il
                 frammento migliore e' quello su cui il validatore ha giudicato.

   LIMITE DA DICHIARARE. Le righe giudicate sono nate dalla ricerca di luglio
   (e5 sui frammenti): le riprese note sono per costruzione quelle che e5 sa
   trovare. Il confronto favorisce e5 sui frammenti, non lo sfavorisce.
   Nel disturbo possono esserci riprese vere mai viste: «disturbo» e' cio' che
   nessuno ha giudicato, non cio' che e' sbagliato.

   Uso:  python3 tools/076_catalogo_parziale.py costruisci   (sul Mac)
         python3 tools/076_catalogo_parziale.py misura        (sulla GPU)
"""
import collections, json, pathlib, random, re, sys, time
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
T = QUI/'training'
CAT = T/'catalogo_parziale.json'
ISTR = ('Given a legal proposition established in a specific court judgment, retrieve passages from other '
        'cases that adopt this same line of reasoning as their own, not passages that merely discuss the '
        'same topic or that derive a similar conclusion from other legal sources')


def costruisci():
    B = __import__('007_build_chunks')
    g = json.loads((QUI/'giudizi-umani-2026-09-22.json').read_text(encoding='utf-8'))
    sem = [r for r in g if r.get('proposto_rete') == 'semantica']
    giudicati = sorted({r['file'] for r in sem})
    tutti = sorted(str(p.relative_to(QUI)) for p in (QUI/'markdown').rglob('*.md'))
    urgenda = {f for f in tutti if 'urgenda-foundation' in f}
    altri = [f for f in tutti if f not in set(giudicati) and f not in urgenda]
    disturbo = random.Random(20260923).sample(altri, 300)
    pagine, frammenti, pos_pagina = [], [], {}
    for f in giudicati + disturbo:
        meta, corpo, base = B.leggi(QUI/f)
        marks = B.pagine(corpo)
        doc = meta.get('document_id') or pathlib.Path(f).stem
        # pagine: il testo fra un segno e il successivo
        confini = marks + [(len(corpo), None)]
        for (a, num), (b, _) in zip(confini, confini[1:]):
            t = re.sub(r'[ \t]+', ' ', B.PAGE_RE.sub(' ', corpo[a:b])).strip()
            if len(t) >= 200:
                pagine.append({'doc': doc, 'file': f, 'pagina': num, 'testo': t[:12000], 'disturbo': f in disturbo})
        for a, b in B.frammenti(corpo):
            t = re.sub(r'[ \t]+', ' ', B.PAGE_RE.sub(' ', corpo[max(0, a-B.OVERLAP):b])).strip()
            if len(t) >= B.MIN_CHUNK // 2:
                frammenti.append({'doc': doc, 'file': f, 'pagina': B.pagina_di(marks, a), 'pagina_fine': B.pagina_di(marks, b),
                                  'da': base+max(0, a-B.OVERLAP), 'a': base+b, 'testo': t, 'disturbo': f in disturbo})
        pos_pagina[f] = (base, marks)
    # righe giudicate: documento, pagina, punto, sonda, etichetta corretta, parte
    etich = {}
    for parte in ('addestramento', 'prova'):
        for l in open(T/f'urgenda_decisione_{parte}_corrette.jsonl', encoding='utf-8'):
            x = json.loads(l); etich[x['id']] = (x['etichetta'], parte, x['sonda_testo'])
    righe = []
    for r in sem:
        if r['_id'] not in etich:
            continue
        base, marks = pos_pagina[r['file']]
        e, parte, sonda = etich[r['_id']]
        righe.append({'id': r['_id'], 'doc': r['document_id'], 'file': r['file'], 'etichetta': e, 'parte': parte, 'sonda': sonda,
                      'pagina': B.pagina_di(marks, r['char_start'] - base), 'char': r['char_start']})
    CAT.write_text(json.dumps({'pagine': pagine, 'frammenti': frammenti, 'righe': righe}, ensure_ascii=False), encoding='utf-8')
    print(f'documenti giudicati {len(giudicati)}, di disturbo {len(disturbo)}; pagine {len(pagine)}, frammenti {len(frammenti)}; '
          f'righe {len(righe)} (prova {sum(r["parte"]=="prova" for r in righe)}, vere in prova {sum(r["parte"]=="prova" and r["etichetta"] for r in righe)})')


def misura():
    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import PeftModel
    c = json.loads(CAT.read_text(encoding='utf-8'))
    P, Fr, R = c['pagine'], c['frammenti'], [r for r in c['righe'] if r['parte'] == 'prova']
    sonde = sorted({r['sonda'] for r in R})
    print(f'catalogo: {len(P)} pagine, {len(Fr)} frammenti; {len(sonde)} sonde; righe di prova {len(R)} ({sum(r["etichetta"] for r in R)} vere)', flush=True)

    def qwen(adattatore=None):
        # Adattatore addestrato SOLO sul lato della domanda (§62.7): le pagine e i
        # frammenti si leggono col modello di base, le sonde con l'adattatore.
        tok = AutoTokenizer.from_pretrained('Qwen/Qwen3-Embedding-4B', padding_side='left')
        m = AutoModel.from_pretrained('Qwen/Qwen3-Embedding-4B', torch_dtype=torch.bfloat16).cuda()
        if adattatore:
            m = PeftModel.from_pretrained(m, adattatore)
        m.eval()
        import contextlib

        def enc(testi, domanda, maxlen=2048, batch=32):
            out = []
            spento = m.disable_adapter() if (adattatore and not domanda) else contextlib.nullcontext()
            with torch.no_grad(), spento:
                for i in range(0, len(testi), batch):
                    t = [f'Instruct: {ISTR}\nQuery:{x}' if domanda else x for x in testi[i:i+batch]]
                    e = tok(t, padding=True, truncation=True, max_length=maxlen, return_tensors='pt').to('cuda')
                    with torch.autocast('cuda', dtype=torch.bfloat16):
                        h = m(**e).last_hidden_state[:, -1]
                    out.append(F.normalize(h.float(), dim=-1).cpu())
            return torch.cat(out).numpy()
        return enc

    def e5():
        tok = AutoTokenizer.from_pretrained('intfloat/multilingual-e5-large')
        m = AutoModel.from_pretrained('intfloat/multilingual-e5-large').cuda().eval()

        def enc(testi, domanda, maxlen=512, batch=64):
            out = []
            with torch.no_grad():
                for i in range(0, len(testi), batch):
                    e = tok(['passage: ' + x for x in testi[i:i+batch]], padding=True, truncation=True, max_length=512, return_tensors='pt').to('cuda')
                    h = m(**e).last_hidden_state; k = e['attention_mask'].unsqueeze(-1).float()
                    out.append(F.normalize((h*k).sum(1)/k.sum(1), dim=-1).cpu())
            return torch.cat(out).numpy()
        return enc

    ada = str(T/'lora_primo_qwen4b_solodomanda_1'/'passata_1')
    # Ridotte a tre il 23/09/2026 sera: con cinque, sulla A100 condivisa con un
    # addestramento, dopo mezz'ora non era finita la prima. Le tre che rispondono
    # alla domanda del PI: il sistema di oggi, e il primo modello addestrato sui
    # frammenti e sulle pagine.
    configurazioni = [('Qwen, domanda addestrata, pagine', qwen, ada, 'pagine'),
                      ('Qwen, domanda addestrata, frammenti', qwen, ada, 'frammenti'),
                      ('e5, frammenti (oggi)', e5, None, 'frammenti')]
    vere = collections.defaultdict(set); bocciate = collections.defaultdict(set); punto = {}
    for r in R:
        (vere if r['etichetta'] else bocciate)[r['sonda']].add((r['doc'], r['pagina']))
        if r['etichetta']:
            punto[(r['sonda'], r['doc'], r['pagina'])] = r['char']
    esiti, cache = {}, {}
    for nome, fab, adatt, unita in configurazioni:
        t0 = time.time()
        chiave = (fab.__name__, adatt)
        if chiave not in cache:
            cache.clear(); torch.cuda.empty_cache()
            cache[chiave] = fab(adatt) if adatt else fab()
        enc = cache[chiave]
        U = P if unita == 'pagine' else Fr
        V = enc([u['testo'] for u in U], False)
        Q = dict(zip(sonde, enc(sonde, True)))
        riga = {}
        for K in (50, 200, 500):
            tr = bo = di = tot_v = 0; pun_ok = pun_n = 0
            for s in sonde:
                ordine = np.argsort(-(V @ Q[s]))[:K]
                coperte = set()
                for i in ordine:
                    u = U[i]
                    for p in range(u['pagina'], u.get('pagina_fine', u['pagina']) + 1):
                        coperte.add((u['doc'], p))
                    di += u['disturbo']
                tr += len(vere[s] & coperte); tot_v += len(vere[s]); bo += len(bocciate[s] & coperte)
                if unita == 'pagine' and K == 200:
                    # puntamento: dentro ogni pagina vera trovata, il frammento migliore copre il punto giudicato?
                    idx_fr = collections.defaultdict(list)
                    for j, f in enumerate(Fr):
                        idx_fr[(f['doc'], f['pagina'])].append(j)
                    for d, p in vere[s] & coperte:
                        js = idx_fr.get((d, p), [])
                        if not js:
                            continue
                        vf = enc([Fr[j]['testo'] for j in js], False)
                        migliore = Fr[js[int(np.argmax(vf @ Q[s]))]]
                        pun_n += 1; pun_ok += migliore['da'] <= punto[(s, d, p)] <= migliore['a']
            riga[K] = {'trovate': tr, 'di': tot_v, 'bocciate': bo, 'disturbo': di/(K*len(sonde))}
            if pun_n:
                riga['puntamento'] = (pun_ok, pun_n)
            print(f'  {nome:28s} primi {K:3d}: vere trovate {tr}/{tot_v} ({100*tr/max(tot_v,1):.0f}%)  bocciate {bo}  '
                  f'dal disturbo {100*di/(K*len(sonde)):.0f}%', flush=True)
        if 'puntamento' in riga:
            ok, n = riga['puntamento']
            print(f'  {nome:28s} puntamento: il frammento migliore della pagina e\' quello giudicato in {ok}/{n} pagine vere', flush=True)
        print(f'  [{time.time()-t0:.0f}s]', flush=True)
        esiti[nome] = riga
    (T/'esiti_catalogo_parziale.json').write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    costruisci() if sys.argv[1] == 'costruisci' else misura()
