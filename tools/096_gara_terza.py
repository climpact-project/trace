"""LA GARA, terza parte (PI, 25/09/2026 sera: «cerca altri modelli, fai di tutto»).
   Tutti i modelli recenti per cercare e per mettere in ordine che stanno su una H100, stessa prova
   (133 righe di Urgenda, sonda contro finestra di pagina, AUC, NON addestrati).
   Ogni modello nel formato che dichiara: `encode_query`/`encode_document` di sentence-transformers
   applicano i prompt della sua scheda. Se il suo prompt di domanda e' un'istruzione («Instruct: ...»)
   si misura anche con la nostra istruzione giuridica. Errori e licenze si registrano, non fermano la gara."""
import gc, json, pathlib, sys, time, traceback
import numpy as np, torch
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_prova_unita = __import__('109_prova_unita')
auc = _m_prova_unita.auc
_m_catalogo_parziale = __import__('076_catalogo_parziale')
ISTR_CERCA = _m_catalogo_parziale.ISTR
_m_prova_riordinatori = __import__('027_prova_riordinatori')
ISTR = _m_prova_riordinatori.ISTR
from sentence_transformers import SentenceTransformer, CrossEncoder
righe = [x for x in (json.loads(l) for l in open(QUI/'training'/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8'))
         if x['frammento'] and x.get('finestra_larga')]
y = np.array([x['etichetta'] for x in righe]); sonde = [x['sonda_testo'] for x in righe]; pagine = [x['finestra'] for x in righe]
USCITA = QUI/'training'/'esiti_gara_terza.json'
esiti = json.loads(USCITA.read_text()) if USCITA.exists() else {}

CERCA = ['Octen/Octen-Embedding-8B', 'nvidia/llama-embed-nemotron-8b', 'microsoft/harrier-oss-v1-27b',
         'perplexity-ai/pplx-embed-v1-4b', 'tencent/KaLM-Embedding-Gemma3-12B-2511', 'Qwen/Qwen3-VL-Embedding-2B',
         'jinaai/jina-embeddings-v5-text-small', 'google/embeddinggemma-300m', 'tencent/WeMM-Embedding-9B',
         'zeroentropy/zembed-1-embedding', 'voyageai/voyage-4-nano', 'microsoft/harrier-oss-v1-270m',
         'nvidia/Nemotron-3-Embed-1B-BF16', 'ibm-granite/granite-embedding-311m-multilingual-r2']
ORDINA = ['Qwen/Qwen3-VL-Reranker-2B', 'nvidia/llama-nemotron-rerank-1b-v2', 'zeroentropy/zerank-1-reranker',
          'jinaai/jina-reranker-v3', 'Contrastive-LM/CLM-v0.1-8B', 'Qwen/Qwen3-Reranker-8B']


def salva():
    USCITA.write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding='utf-8')


def libera():
    gc.collect(); torch.cuda.empty_cache()


for nome in CERCA:
    if nome in esiti and 'errore' not in esiti[nome]:
        continue
    t0 = time.time(); m = None
    try:
        m = SentenceTransformer(nome, trust_remote_code=True, model_kwargs={'torch_dtype': torch.bfloat16}); m.max_seq_length = min(2560, m.max_seq_length or 2560)
        nz = lambda v: v / np.linalg.norm(v, axis=1, keepdims=True)
        D = nz(np.asarray(m.encode_document(pagine, batch_size=2), dtype=float))
        Q = nz(np.asarray(m.encode_query(sonde, batch_size=8), dtype=float))
        r = {'suo_formato': round(float(auc(y, (Q*D).sum(1))), 3), 'prompts': list((m.prompts or {}).keys())}
        pq = (m.prompts or {}).get('query') or ''
        if 'Instruct' in pq or 'instruct' in pq:
            Q2 = nz(np.asarray(m.encode(sonde, batch_size=8, prompt=f'Instruct: {ISTR_CERCA}\nQuery: '), dtype=float))
            r['istruzione_giuridica'] = round(float(auc(y, (Q2*D).sum(1))), 3)
        esiti[nome] = r; print(f'  CERCA  {nome:50s} {r}  [{time.time()-t0:.0f}s]', flush=True)
    except Exception as e:
        esiti[nome] = {'errore': repr(e)[:300]}; print(f'  CERCA  {nome}: ERRORE {e!r}'[:300], flush=True)
    m = None; libera(); salva()

for nome in ORDINA:
    if nome in esiti and 'errore' not in esiti[nome]:
        continue
    t0 = time.time(); m = None
    try:
        m = CrossEncoder(nome, trust_remote_code=True, model_kwargs={'torch_dtype': torch.bfloat16}); m.max_length = 2560
        try:
            s = m.predict(list(zip(sonde, pagine)), batch_size=2, prompt=ISTR['ripresa'])
            modo = 'con istruzione'
        except TypeError:
            s = m.predict(list(zip(sonde, pagine)), batch_size=2); modo = 'senza istruzione'
        a = round(float(auc(y, np.asarray(s, dtype=float))), 3)
        esiti[nome] = {'auc': a, 'modo': modo}; print(f'  ORDINA {nome:50s} AUC {a} ({modo})  [{time.time()-t0:.0f}s]', flush=True)
    except Exception as e:
        esiti[nome] = {'errore': repr(e)[:300]}; print(f'  ORDINA {nome}: ERRORE {e!r}'[:300], flush=True)
    m = None; libera(); salva()
print(json.dumps(esiti, ensure_ascii=False, indent=1))
