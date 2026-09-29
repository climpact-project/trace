"""Page index built with the BASE embedding model, computed once.

   Only the query side of the retrieval model is fine-tuned; pages are encoded by the base model, so
   the index is built once and need not be rebuilt at each retraining. Page-level search was measured
   to add no more noise than chunk-level search. A page is the text between two page markers, at least
   200 characters, truncated to 12,000; the model reads its first 2,048 tokens.

   Usage:  python3 tools/indice_pagine.py prepara                       (local machine: writes index/pagine/pagine.jsonl.gz)
           python3 tools/indice_pagine.py costruisci --parte 0 --parti 4 (GPU: vectors for one quarter of the pages)
           python3 tools/indice_pagine.py costruisci --finestre --modello pplx4b --parte 0 --parti 8

   Windows (--finestre). With whole-page vectors, half of the human-confirmed uptakes (40 of 80) fell
   outside the top 500 for every probe and did not surface even at 5,000, although the row-to-page link
   was correct (99 of 102 confirmed passages lie on the indicated page): a long page dilutes the relevant
   sentence. Each page is therefore split into windows of about 1,200 characters with 300 of overlap,
   each window gets its own vector, and a page scores as its best window.
"""
import argparse, gzip, json, pathlib, re, sys, time
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
OUT = QUI/'index'/'pagine'


def prepara():
    import build_chunks as B
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0; t0 = time.time()
    with gzip.open(OUT/'pagine.jsonl.gz', 'wt', encoding='utf-8') as f:
        for p in sorted((QUI/'markdown').rglob('*.md')):
            meta, corpo, base = B.leggi(p)
            marks = B.pagine(corpo)
            doc = meta.get('document_id') or p.stem
            confini = marks + [(len(corpo), None)]
            for (a, num), (b, _) in zip(confini, confini[1:]):
                t = re.sub(r'[ \t]+', ' ', B.PAGE_RE.sub(' ', corpo[a:b])).strip()
                if len(t) >= 200:
                    f.write(json.dumps({'id': f'{doc}#p{num}', 'doc': doc, 'file': str(p.relative_to(QUI)),
                                        'pagina': num, 'da': base + a, 'a': base + b, 'testo': t[:12000]}, ensure_ascii=False) + '\n')
                    n += 1
    print(f'pagine {n} in {time.time()-t0:.0f}s -> {OUT/"pagine.jsonl.gz"}')


# name -> (model, pooling, page prefix); Perplexity uses mean pooling, no prefix, and its own remote code
MODELLI = {'qwen4b': ('Qwen/Qwen3-Embedding-4B', 'ultimo', ''), 'pplx4b': ('perplexity-ai/pplx-embed-v1-4b', 'media', '')}


FIN_LUNGA, FIN_PASSO = 1200, 900


def finestre(testo):
    """Windows of ~1,200 characters advancing by 900 (300 overlap), cut on whitespace."""
    out, i, n = [], 0, len(testo)
    while i < n:
        j = min(n, i + FIN_LUNGA)
        if j < n:
            k = testo.rfind(' ', i + FIN_LUNGA - 150, j)
            j = k if k > i else j
        out.append(testo[i:j].strip())
        if j >= n:
            break
        k = testo.find(' ', i + FIN_PASSO)
        i = k + 1 if 0 < k < j else i + FIN_PASSO
    return [t for t in out if len(t) >= 80] or [testo]


def costruisci(parte, parti, lotto, nome='qwen4b', con_finestre=False):
    import numpy as np, torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    righe = [json.loads(l) for i, l in enumerate(gzip.open(OUT/'pagine.jsonl.gz', 'rt', encoding='utf-8')) if i % parti == parte]
    if con_finestre:
        righe = [{'id': f"{r['id']}#w{k}", 'testo': t} for r in righe for k, t in enumerate(finestre(r['testo']))]
    print(f'parte {parte}/{parti}: {len(righe)} {"finestre" if con_finestre else "pagine"}', flush=True)
    MOD, POOL, PD = MODELLI[nome]
    fuori = OUT if (nome == 'qwen4b' and not con_finestre) else QUI/'index'/(f'finestre_{nome}' if con_finestre else f'pagine_{nome}')
    fuori.mkdir(parents=True, exist_ok=True)
    maxtok = 512 if con_finestre else 2048
    tok = AutoTokenizer.from_pretrained(MOD, padding_side='left', trust_remote_code=True)
    m = AutoModel.from_pretrained(MOD, dtype=torch.bfloat16, trust_remote_code=True).cuda().eval()
    ordine = sorted(range(len(righe)), key=lambda i: len(righe[i]['testo']))   # batches of similar length: less padding
    V = np.zeros((len(righe), m.config.hidden_size), dtype=np.float16); t0 = time.time()
    with torch.no_grad():
        for k in range(0, len(ordine), lotto):
            idx = ordine[k:k+lotto]
            e = tok([PD + righe[i]['testo'] for i in idx], padding=True, truncation=True, max_length=maxtok, return_tensors='pt').to('cuda')
            hs = m(**e).last_hidden_state
            if POOL == 'media':
                mk = e['attention_mask'].unsqueeze(-1).to(hs.dtype); h = (hs*mk).sum(1)/mk.sum(1)
            else:
                h = hs[:, -1]
            V[idx] = F.normalize(h.float(), dim=-1).cpu().numpy().astype(np.float16)
            if (k // lotto) % 200 == 0:
                fatte = k + len(idx); v = fatte / (time.time()-t0)
                print(f'  {fatte}/{len(righe)}  {v:.1f} pagine/s  mancano {(len(righe)-fatte)/v/60:.0f} min', flush=True)
    np.save(fuori/f'vettori_{parte}.npy', V)
    json.dump([r['id'] for r in righe], open(fuori/f'ids_{parte}.json', 'w'))
    json.dump({'modello': MOD, 'pooling': POOL, 'max_token': maxtok, 'finestre': con_finestre, 'parte': parte, 'parti': parti, 'pagine': len(righe),
               'secondi': round(time.time()-t0)}, open(fuori/f'manifesto_{parte}.json', 'w'), indent=1)
    print(f'fatto in {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase'); ap.add_argument('--parte', type=int, default=0)
    ap.add_argument('--parti', type=int, default=1); ap.add_argument('--lotto', type=int, default=16); ap.add_argument('--modello', default='qwen4b')
    ap.add_argument('--finestre', action='store_true')
    a = ap.parse_args()
    prepara() if a.fase == 'prepara' else costruisci(a.parte, a.parti, a.lotto, a.modello, a.finestre)
