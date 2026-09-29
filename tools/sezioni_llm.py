"""Section tree of a filing read by a language model (PageIndex-style experiment).

   Rationale. On filings with an embedded PDF outline (67 of the 314 citing Urgenda), the SECTION separates the
   continuation of a citation from same-topic pages better than page distance (`sezioni_atto.py`). The other 247
   have no outline, and inferring headings from font size does not work (30% recovered, 662 invented). Following
   PageIndex (VectifyAI), headings are read by a model: here Qwen3-14B, not fine-tuned, on a single GPU.

   Method. Each filing is split into blocks of 4 pages, with page markers. The model lists the headings of parts,
   sections and subsections appearing in the text, COPIED verbatim, with page and level; no running headers, no
   footnotes. The output is measured against filings with a true outline before being used on the others.

   Phases:
     prepara  local machine -> training/sezioni/blocchi.jsonl (to be copied to the GPU server)
     leggi    GPU server    -> training/sezioni/titoli.jsonl (vLLM, Qwen3-14B, one GPU)
     conta    local machine -> measurement against the true outline; high-scoring window pages: same section as
                               the citation?
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
    # A block in Korean or Japanese script can exceed the context window: the text is truncated proportionally and
    # the truncation is recorded on the row (`tagliato`).
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
    """Return {document: [(level, title, page)]} from the model-read headings, in page order."""
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
    from sezioni_atto import pdf_di, sezione
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
    # high-scoring window pages: same section as the citation?
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
