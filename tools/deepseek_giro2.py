"""DEEPSEEK, SECONDO GIRO: la domanda corretta, cinque letture per riga.

   DUE COSE MISURATE INSIEME.
   1. La domanda a catena nella seconda versione (`ISTRUZIONI_CATENA_V2` in
      giudica_llm.py), contro la prima. La seconda e' stata scritta leggendo
      gli errori sulle righe di PROVA; per non tararla sulla prova si misurano
      tutte e due le versioni anche sulle 257 righe di ADDESTRAMENTO, che
      nessuno ha letto per scriverla. Se il guadagno c'e' anche li', non e'
      un adattamento alla prova.
   2. Cinque letture indipendenti per riga (campionamento a temperatura 0,6,
      come raccomanda DeepSeek per il modo che ragiona). Il numero di letture
      che dicono RIPRESA, da 0 a 5, e' un punteggio: si puo' scegliere la
      soglia (una lettura su cinque per non perdere nulla, la maggioranza per
      la precisione) e si puo' calcolare l'AUC, confrontabile con quella del
      riordinatore.
"""
import argparse, json, pathlib, sys, time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
from giudica_llm import costruisci, estrai  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modello', required=True)
    ap.add_argument('--letture', type=int, default=5)
    ap.add_argument('--memoria', type=float, default=0.85)
    a = ap.parse_args()
    sys.path.insert(0, str(pathlib.Path(a.modello)/'encoding'))
    from encoding_dsv4 import encode_messages
    from vllm import LLM, SamplingParams
    T = QUI/'training'
    t0 = time.time()
    llm = LLM(model=a.modello, max_model_len=32768, gpu_memory_utilization=a.memoria, trust_remote_code=True)
    print(f'caricato in {time.time()-t0:.0f}s', flush=True)
    sp = SamplingParams(n=a.letture, temperature=0.6, top_p=0.95, max_tokens=8000, seed=20260923)
    for parte in ('prova', 'addestramento'):
        righe = [json.loads(x) for x in open(T/f'urgenda_decisione_{parte}_corrette_larghe.jsonl', encoding='utf-8') if x.strip()]
        for versione in (1, 2):
            t0 = time.time()
            pr = [encode_messages([{'role': 'user', 'content': costruisci(r, versione)}], thinking_mode='thinking') for r in righe]
            out = llm.generate(pr, sp)
            fuori = []
            for r, o in zip(righe, out):
                letture = []
                for c in o.outputs:
                    t = c.text.rpartition('</think>')[2] if '</think>' in c.text else c.text
                    letture.append(estrai(t))
                fuori.append({'id': r['id'], 'etichetta': r['etichetta'], 'sonda_titolo': r.get('sonda_titolo'),
                              'case_id': r.get('case_id'), 'letture': letture,
                              'voti_ripresa': sum(1 for g in letture if g.get('esito') == 'RIPRESA'),
                              'token': sum(len(c.token_ids) for c in o.outputs)})
            (T/f'deepseek_v{versione}_{parte}_{a.letture}letture.json').write_text(
                json.dumps(fuori, ensure_ascii=False, indent=1), encoding='utf-8')
            y = [x['etichetta'] for x in fuori]
            for soglia in range(1, a.letture + 1):
                p = [x['voti_ripresa'] >= soglia for x in fuori]
                tp = sum(u and q for u, q in zip(y, p)); P = sum(p)
                print(f'  v{versione} {parte:13s} almeno {soglia}/{a.letture}: propone {P:3d}  precisione {tp/max(P,1):.0%}  trova {tp}/{sum(y)} = {tp/max(sum(y),1):.0%}', flush=True)
            print(f'v{versione} {parte}: {len(righe)} righe in {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
