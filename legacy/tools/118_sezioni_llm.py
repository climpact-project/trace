"""L'ALBERO DELLE SEZIONI LETTO DA UN MODELLO (29/09/2026, prova tipo PageIndex, decisa col PI).

   Perche'. Sugli atti che hanno l'indice nel PDF (67 su 314 di quelli che citano Urgenda) la SEZIONE distingue il
   seguito di una citazione dallo stesso tema meglio del numero di pagine (`117_sezioni_atto.py`, §63.28). Negli altri
   247 l'indice non c'e', e ricavare i titoli dal carattere non funziona (30% ritrovati, 662 inventati). PageIndex
   (VectifyAI) li fa leggere a un modello: qui Qwen3-14B, non addestrato, su una GPU di ReCaS.

   Come. Ogni atto a blocchi di 4 pagine, con i segni di pagina. Il modello elenca i titoli di parti, sezioni e
   sottosezioni che compaiono nel testo, COPIATI com'e' scritti, con pagina e livello. Niente intestazioni di pagina,
   niente note. Si misura sugli atti con l'indice vero prima di usarlo sugli altri.

   Fasi:
     prepara  Mac   -> training/sezioni/blocchi.jsonl (da caricare su ReCaS)
     leggi    ReCaS -> training/sezioni/titoli.jsonl (vLLM, Qwen3-14B, una GPU)
     conta    Mac   -> misura contro l'indice vero; pagine alte della finestra: stessa sezione della citazione?
"""
import argparse, collections, gzip, json, pathlib, re, sys
QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'
S = T/'sezioni'
BLOCCO = 4

ISTRUZIONI = """Below are pages {da}-{a} of a legal document (a court filing or judgment). Each page starts with a line «=== PAGE n ===».

List the HEADINGS of the document's own structure that appear in these pages: titles of parts, chapters, sections and subsections (for example «IV. THE LAW», «A. Positive obligations under Article 8», «3.2 The duty of care», «Facts», «Conclusions»). Copy each heading exactly as written.

Do NOT list: running headers or footers repeated on every page, page numbers, footnotes, numbered paragraphs that are ordinary text (a paragraph «54. The court considers that...» is not a heading), table of contents entries, list items inside a paragraph.

Level: 1 = top-level part of the document, 2 = section inside a part, 3 = anything deeper.

Answer ONLY with JSON: {{"headings": [{{"page": n, "level": 1, "text": "..."}}]}}. If there is no heading in these pages: {{"headings": []}}.

{testo}"""


def prepara():
    S.mkdir(parents=True, exist_ok=True)
    R = [json.loads(l) for l in open(T/'lessicali_urgenda_righe.jsonl', encoding='utf-8')]
    docs = {r['document_id'] for r in R}
    pagine = collections.defaultdict(dict)
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l)
            d, n = x['id'].split('#p')
            if d in docs:
                pagine[d][int(n)] = x['testo']
    n = 0
    with open(S/'blocchi.jsonl', 'w', encoding='utf-8') as out:
        for d in sorted(pagine):
            nums = sorted(pagine[d])
            for i in range(0, len(nums), BLOCCO):
                pp = nums[i:i + BLOCCO]
                testo = '\n'.join(f'=== PAGE {p} ===\n{pagine[d][p][:6000]}' for p in pp)
                out.write(json.dumps({'id': f'{d}#{pp[0]}', 'documento': d, 'pagine': pp,
                                      'domanda': ISTRUZIONI.format(da=pp[0], a=pp[-1], testo=testo)}, ensure_ascii=False) + '\n')
                n += 1
    print(f'{len(pagine)} atti, {sum(len(v) for v in pagine.values())} pagine, {n} blocchi -> {S/"blocchi.jsonl"}')


def leggi(a):
    from vllm import LLM, SamplingParams
    B = [json.loads(l) for l in open(a.blocchi, encoding='utf-8')]
    llm = LLM(model=a.modello, max_model_len=32768, gpu_memory_utilization=0.90)
    sp = SamplingParams(temperature=0, max_tokens=1200)
    # Un blocco in scrittura coreana o giapponese puo' superare il contesto: si taglia il testo in proporzione, e il
    # taglio resta scritto sulla riga (`tagliato`).
    tok = llm.get_tokenizer()
    tagliati = set()
    for b in B:
        n = len(tok.encode(b['domanda']))
        if n > 30000:
            b['domanda'] = b['domanda'][:int(len(b['domanda']) * 30000 / n * 0.95)]
            tagliati.add(b['id'])
    print('blocchi tagliati', len(tagliati), flush=True)
    msgs = [[{'role': 'user', 'content': b['domanda']}] for b in B]
    uscite = llm.chat(msgs, sp, chat_template_kwargs={'enable_thinking': False})
    with open(a.uscita, 'w', encoding='utf-8') as f:
        for b, u in zip(B, uscite):
            t = u.outputs[0].text
            m = re.search(r'\{.*\}', t, re.S)
            try:
                h = json.loads(m.group(0))['headings'] if m else None
            except Exception:
                h = None
            f.write(json.dumps({'id': b['id'], 'documento': b['documento'], 'pagine': b['pagine'], 'titoli': h,
                                'tagliato': b['id'] in tagliati,
                                'grezzo': None if h is not None else t[:2000]}, ensure_ascii=False) + '\n')
    print('fatto', len(B))


def albero(righe):
    """[(livello, titolo, pagina)] per documento, dai titoli letti, nell'ordine delle pagine."""
    A = collections.defaultdict(list)
    for r in righe:
        for h in (r['titoli'] or []):
            try:
                p = int(h['page']); lv = min(max(int(h.get('level') or 2), 1), 3)
            except Exception:
                continue
            if p in r['pagine'] and str(h.get('text') or '').strip():
                A[r['documento']].append((lv, h['text'].strip(), p))
    for d in A:
        A[d].sort(key=lambda x: x[2])
    return A


def conta():
    import fitz, glob
    sys.path.insert(0, str(QUI/'tools'))
    _m_sezioni_atto = __import__('117_sezioni_atto')
    pdf_di = _m_sezioni_atto.pdf_di
    sezione = _m_sezioni_atto.sezione
    righe = [json.loads(l) for l in open(S/'titoli.jsonl', encoding='utf-8')]
    rotte = sum(1 for r in righe if r['titoli'] is None)
    A = albero(righe)
    P = pdf_di()
    veri = trovati = inventati = n = 0
    for d in A:
        if d not in P or not P[d].exists():
            continue
        v = fitz.open(P[d]).get_toc()
        if len(v) < 3:
            continue
        n += 1
        pv, pm = {pg for _, _, pg in v}, {pg for _, _, pg in A[d]}
        veri += len(pv); trovati += len(pv & pm); inventati += len(pm - pv)
    print(f'blocchi {len(righe)}, risposte illeggibili {rotte}; atti con albero {len(A)}')
    print(f'contro l\'indice vero ({n} atti): pagine con titolo {veri}, ritrovate {trovati} ({trovati / max(veri, 1):.0%}); '
          f'pagine con titoli letti che l\'indice non ha {inventati}')
    # le pagine alte della finestra: stessa sezione della citazione?
    R = [json.loads(l) for l in open(T/'lessicali_urgenda_righe.jsonl', encoding='utf-8')]
    cit = collections.defaultdict(set)
    for r in R:
        if r.get('pagina'):
            cit[r['document_id']].add(int(r['pagina']))
    alte = collections.defaultdict(float)
    for f in sorted(glob.glob(str(T/'principi'/'urgenda_finestra_punteggi_*.jsonl'))):
        for l in open(f):
            x = json.loads(l)
            alte[x['pagina_id']] = max(alte[x['pagina_id']], x['punteggio'])
    c, tot = collections.Counter(), collections.Counter()
    for pid, v in alte.items():
        d, p = pid.split('#p'); p = int(p)
        if v < 0.8 or d not in cit or d not in A:
            continue
        cp = min(cit[d], key=lambda q: abs(q - p)); dl = p - cp
        cl = ('pagina della citazione' if dl == 0 else 'dentro la finestra' if -2 <= dl <= 3
              else 'fuori, entro 10' if abs(dl) <= 10 else 'fuori, oltre 10')
        tot[cl] += 1
        t = A[d]
        c[(cl, 'stessa sezione' if sezione(t, p) == sezione(t, cp)
            else 'stessa parte' if sezione(t, p, 1) == sezione(t, cp, 1) else 'altrove')] += 1
    for cl in ('pagina della citazione', 'dentro la finestra', 'fuori, entro 10', 'fuori, oltre 10'):
        print(f"  {cl}: {tot[cl]}; stessa sezione {c[(cl, 'stessa sezione')]}, stessa parte {c[(cl, 'stessa parte')]}, "
              f"altrove {c[(cl, 'altrove')]}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'leggi', 'conta'])
    ap.add_argument('--blocchi', default=str(S/'blocchi.jsonl')); ap.add_argument('--uscita', default=str(S/'titoli.jsonl'))
    ap.add_argument('--modello', default='Qwen/Qwen3-14B')
    a = ap.parse_args()
    prepara() if a.fase == 'prepara' else leggi(a) if a.fase == 'leggi' else conta()
