"""LA GARA, parte Jina (richiesta dal PI il 25/09/2026): stessa prova di `094_gara_modelli.py`.
   Licenza CC BY-NC 4.0: si misurano, ma adattatori addestrati su questi non si potrebbero
   pubblicare con licenza libera. Da dichiarare se vincessero."""
import json, pathlib, sys, time, traceback, collections
import numpy as np, torch
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_prova_unita = __import__('109_prova_unita')
auc = _m_prova_unita.auc
righe = [x for x in (json.loads(l) for l in open(QUI/'training'/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8'))
         if x['frammento'] and x.get('finestra_larga')]
y = np.array([x['etichetta'] for x in righe]); sonde = [x['sonda_testo'] for x in righe]; pagine = [x['finestra'] for x in righe]
esiti = {}
try:
    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    m = SentenceTransformer('jinaai/jina-embeddings-v5-omni-small', trust_remote_code=True,
                            model_kwargs={'default_task': 'retrieval', 'torch_dtype': torch.bfloat16})
    Q = m.encode_query(sonde, normalize_embeddings=True, batch_size=8)
    D = m.encode_document(pagine, normalize_embeddings=True, batch_size=4)
    a = auc(y, (Q*D).sum(1)); esiti['Jina embeddings v5 omni small'] = round(float(a), 3)
    print(f'  CERCA  Jina embeddings v5 omni small  AUC {a:.3f}  [{time.time()-t0:.0f}s]', flush=True)
    del m; torch.cuda.empty_cache()
except Exception as e:
    esiti['Jina embeddings v5'] = 'errore: ' + repr(e)[:300]; traceback.print_exc()
try:
    from transformers import AutoModel
    t0 = time.time()
    m = AutoModel.from_pretrained('jinaai/jina-reranker-v3.5', dtype='auto', trust_remote_code=True).cuda().eval()
    s = np.zeros(len(righe))
    gruppi = collections.defaultdict(list)
    for i, q in enumerate(sonde):
        gruppi[q].append(i)
    for q, idx in gruppi.items():
        docs = [pagine[i] for i in idx]
        for r in m.rerank(q, docs):
            k = r['index'] if 'index' in r else docs.index(r['document'])
            s[idx[k]] = r['relevance_score']
    a = auc(y, s); esiti['Jina reranker v3.5'] = round(float(a), 3)
    print(f'  ORDINA Jina reranker v3.5  AUC {a:.3f}  [{time.time()-t0:.0f}s]', flush=True)
except Exception as e:
    esiti['Jina reranker v3.5'] = 'errore: ' + repr(e)[:300]; traceback.print_exc()
(QUI/'training'/'esiti_gara_jina.json').write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding='utf-8')
print(esiti)
