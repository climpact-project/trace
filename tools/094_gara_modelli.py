"""LA GARA: i modelli usciti dopo la scelta del 23/09 contro i nostri Qwen3, stessa prova.

   PERCHE' (PI, 25/09/2026). La scelta di Qwen3-Embedding-4B e Qwen3-Reranker-4B va giustificata
   nel paper anche contro i modelli piu' recenti. Stessa misura del §60-§62: le 133 righe di prova
   di Urgenda (32 vere), la sonda contro la finestra di pagina, AUC. Qui i modelli NON addestrati:
   i due migliori di ciascun ruolo si addestrano dopo, con la stessa ricetta dei nostri.

   Per cercare (distanza fra sonda e pagina): Qwen3-Embedding-4B e 8B (i nostri, rimisurati qui),
   NVIDIA Nemotron-3-Embed-8B (luglio 2026), Qwen3-VL-Embedding-8B (gennaio 2026),
   Microsoft Harrier 0.6B (marzo 2026).
   Per mettere in ordine (sonda e pagina lette insieme): Qwen3-Reranker-4B (il nostro),
   zerank-2 (novembre 2025), Qwen3-VL-Reranker-8B (gennaio 2026).
   Jina v5 e Jina reranker v3.5 esclusi: licenza solo non commerciale, i nostri adattatori non si
   potrebbero pubblicare liberamente.
"""
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
QwenRiordinatore = _m_prova_riordinatori.QwenRiordinatore

righe = [x for x in (json.loads(l) for l in open(QUI/'training'/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8'))
         if x['frammento'] and x.get('finestra_larga')]
y = np.array([x['etichetta'] for x in righe]); sonde = [x['sonda_testo'] for x in righe]; pagine = [x['finestra'] for x in righe]
print(f'righe {len(y)}, vere {y.sum()}', flush=True)
esiti = {}


def libera():
    gc.collect(); torch.cuda.empty_cache()


def cerca(nome, carica, q_kw, d_kw=None):
    t0 = time.time()
    try:
        m = carica(); m.max_seq_length = 2560
        Q = m.encode(sonde, normalize_embeddings=True, batch_size=8, **q_kw)
        D = m.encode(pagine, normalize_embeddings=True, batch_size=4, **(d_kw or {}))
        a = auc(y, (Q*D).sum(1)); esiti[nome] = round(float(a), 3)
        print(f'  CERCA  {nome:45s} AUC {a:.3f}  [{time.time()-t0:.0f}s]', flush=True)
    except Exception as e:
        esiti[nome] = 'errore: ' + repr(e)[:300]; print(f'  CERCA  {nome}: ERRORE {e!r}'[:400], flush=True); traceback.print_exc()
    finally:
        m = None; libera()


def ordina(nome, carica, kw):
    t0 = time.time()
    try:
        m = carica(); m.max_length = 2560
        s = m.predict(list(zip(sonde, pagine)), batch_size=4, **kw)
        a = auc(y, np.asarray(s, dtype=float)); esiti[nome] = round(float(a), 3)
        print(f'  ORDINA {nome:45s} AUC {a:.3f}  [{time.time()-t0:.0f}s]', flush=True)
    except Exception as e:
        esiti[nome] = 'errore: ' + repr(e)[:300]; print(f'  ORDINA {nome}: ERRORE {e!r}'[:400], flush=True); traceback.print_exc()
    finally:
        m = None; libera()


from sentence_transformers import SentenceTransformer, CrossEncoder
ST = lambda n, **k: (lambda: SentenceTransformer(n, model_kwargs={'torch_dtype': torch.bfloat16}, trust_remote_code=True, **k))
QI = {'prompt': f'Instruct: {ISTR_CERCA}\nQuery:'}
cerca('Qwen3-Embedding-4B (nostro, di base)', ST('Qwen/Qwen3-Embedding-4B'), QI)
cerca('Qwen3-Embedding-8B', ST('Qwen/Qwen3-Embedding-8B'), QI)
cerca('Microsoft Harrier 0.6B', ST('microsoft/harrier-oss-v1-0.6b'), {'prompt': f'Instruct: {ISTR_CERCA}\nQuery: '})
cerca('NVIDIA Nemotron-3-Embed-8B', ST('nvidia/Nemotron-3-Embed-8B-BF16'), QI)
cerca('Qwen3-VL-Embedding-8B', ST('Qwen/Qwen3-VL-Embedding-8B'), {'prompt': ISTR_CERCA})

# il nostro riordinatore di base, con la stessa procedura del 23/09 (0,756 misurato allora)
t0 = time.time()
q = QwenRiordinatore('Qwen/Qwen3-Reranker-4B')
a = auc(y, q.punteggi(list(zip(sonde, pagine)), ISTR['ripresa'], 2560)); q.libera(); libera()
esiti['Qwen3-Reranker-4B (nostro, di base)'] = round(float(a), 3); print(f'  ORDINA {"Qwen3-Reranker-4B (nostro, di base)":45s} AUC {a:.3f}  [{time.time()-t0:.0f}s]', flush=True)
CE = lambda n: (lambda: CrossEncoder(n, trust_remote_code=True, model_kwargs={'torch_dtype': torch.bfloat16}))
ordina('zerank-2', CE('zeroentropy/zerank-2-reranker'), {})
ordina('Qwen3-VL-Reranker-8B', CE('Qwen/Qwen3-VL-Reranker-8B'), {'prompt': ISTR['ripresa']})
(QUI/'training'/'esiti_gara_modelli.json').write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(esiti, ensure_ascii=False, indent=1))
