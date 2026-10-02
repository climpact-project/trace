"""TUTTE LE PROVE DI DEEPSEEK V4 FLASH CON UN SOLO CARICAMENTO.

   Il modello impiega circa mezz'ora a partire su GPU (pesi da 160 GB, kernel
   compilati al volo, grafi CUDA): caricarlo una volta per prova sarebbe tempo
   buttato. Qui si carica una volta e si fanno, in quest'ordine:
     1. la domanda a catena sulle 137 righe di prova, modo `thinking`;
     2. la stessa in modo `chat` (senza ragionamento), per il costo sul Mac;
     3. le categorie del codebook sulle 111 righe lessicali, `thinking`,
        senza e con esempi (vedi `077_categoria_llm.py`);
     4. le stesse in modo `chat`.
   Ogni prova scrive il suo file appena finisce, cosi' un'interruzione non
   perde quelle gia' fatte.
"""
import argparse, collections, json, pathlib, random, re, sys, time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_giudica_llm = __import__('023_giudica_llm')
costruisci = _m_giudica_llm.costruisci
estrai = _m_giudica_llm.estrai
CL = __import__('077_categoria_llm')


def dividi(testo):
    if '</think>' in testo:
        r, _, s = testo.rpartition('</think>')
        return r.strip(), s
    return '', testo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modello', required=True)
    ap.add_argument('--memoria', type=float, default=0.85)
    ap.add_argument('--prove', default='catena_thinking,catena_chat,categoria_thinking,categoria_chat')
    a = ap.parse_args()
    sys.path.insert(0, str(pathlib.Path(a.modello)/'encoding'))
    from encoding_dsv4 import encode_messages
    from vllm import LLM, SamplingParams

    T = QUI/'training'
    righe = [json.loads(x) for x in open(T/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8') if x.strip()]
    carica = lambda p: [json.loads(x) for x in open(T/f'urgenda_categoria_{p}.jsonl', encoding='utf-8') if x.strip()]
    ctr, cte = carica('addestramento'), carica('prova')
    defs = CL.definizioni()
    rnd = random.Random(20260923)
    es = []
    for c in CL.CATEGORIE:
        cand = [x for x in ctr if x['categoria'] == c]
        for x in rnd.sample(cand, min(2, len(cand))):
            es.append(f'«{CL.smaschera(x["passaggio"]).strip()}» -> {c}')
    esempi = '\nESEMPI GIA\' CODIFICATI DAL GRUPPO DI RICERCA:\n' + '\n'.join(es) + '\n'

    t0 = time.time()
    llm = LLM(model=a.modello, max_model_len=32768, gpu_memory_utilization=a.memoria, trust_remote_code=True)
    print(f'caricato in {time.time()-t0:.0f}s', flush=True)

    def sp(modo, lungo):
        return SamplingParams(temperature=0.0 if modo == 'chat' else 0.6, top_p=1.0 if modo == 'chat' else 0.95,
                              max_tokens=(1200 if modo == 'chat' else lungo), seed=20260923)

    for prova in a.prove.split(','):
        tipo, modo = prova.split('_')
        t0 = time.time()
        if tipo == 'catena':
            pr = [encode_messages([{'role': 'user', 'content': costruisci(r)}], thinking_mode=modo) for r in righe]
            out = llm.generate(pr, sp(modo, 8000))
            fuori = []
            for r, o in zip(righe, out):
                rag, ris = dividi(o.outputs[0].text)
                fuori.append({'id': r['id'], 'etichetta': r['etichetta'], 'sonda_titolo': r.get('sonda_titolo'),
                              'case_id': r.get('case_id'), 'llm': estrai(ris), 'ragionamento': rag,
                              'token': len(o.outputs[0].token_ids)})
        else:
            pr = [encode_messages([{'role': 'user', 'content': CL.prompt(r, defs, e)}], thinking_mode=modo)
                  for e in ('', esempi) for r in cte]
            out = llm.generate(pr, sp(modo, 6000))
            fuori = {}
            for i, v in enumerate(('zero', 'esempi')):
                rr = []
                for r, o in zip(cte, out[i*len(cte):(i+1)*len(cte)]):
                    rag, t = dividi(o.outputs[0].text)
                    m = re.search(r'"categoria"\s*:\s*"([a-z_]+)"', t)
                    rr.append({'id': r['id'], 'umano': r['categoria'], 'llm': m.group(1) if m else 'ILLEGGIBILE',
                               'motivo': (re.search(r'"motivo"\s*:\s*"([^"]*)"', t) or [None, ''])[1],
                               'ragionamento': rag, 'token': len(o.outputs[0].token_ids)})
                y, p = [x['umano'] for x in rr], [x['llm'] for x in rr]
                acc = sum(u == q for u, q in zip(y, p)) / len(y)
                fuori[v] = {'accuratezza': acc, 'kappa': CL.kappa(y, p), 'righe': rr}
                print(f'  {prova} {v}: accuratezza {acc:.3f} kappa {CL.kappa(y, p):.3f}', flush=True)
        dt = time.time() - t0
        (T/f'deepseek_{prova}.json').write_text(json.dumps(fuori, ensure_ascii=False, indent=1), encoding='utf-8')
        n_tok = sum(len(o.outputs[0].token_ids) for o in out)
        print(f'{prova}: {len(pr)} richieste in {dt:.0f}s, {n_tok} token in uscita ({n_tok/len(pr):.0f} a richiesta)', flush=True)
        if tipo == 'catena':
            print('  esiti:', collections.Counter(x['llm'].get('esito') for x in fuori).most_common(), flush=True)


if __name__ == '__main__':
    main()
