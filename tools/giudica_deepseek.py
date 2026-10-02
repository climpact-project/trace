"""DEEPSEEK V4 FLASH COME LETTORE — lo stesso esame di Qwen3-32B e di Fable.

   PERCHE'. Il lettore della pipeline deve girare sul Mac Studio (256 GB) e
   deve essere un modello aperto: Fable non si puo' usare. DeepSeek V4 Flash
   (284 miliardi di parametri, 13 attivi, pesi FP8/FP4 da 160 GB) ci sta. Qui
   si misura su GPU se legge come serve: stesse 137 righe di prova, stessa
   domanda a catena (`giudica_llm.ISTRUZIONI_CATENA`, con le pagine prima e
   dopo), confronto con Qwen3-32B sulle 137 e con Fable sulle sue 40.

   DUE MODI. `chat` risponde subito; `thinking` ragiona prima di rispondere,
   ed e' il modo che il PI chiede («deve ragionare al contesto delle parole
   del passaggio e piu' attorno»). Si misurano tutti e due: il ragionamento
   costa tempo, e sul Mac il tempo conta.

   Il modello non ha un chat template: la codifica del prompt e' quella
   ufficiale di DeepSeek (`encoding/encoding_dsv4.py` nella cartella dei pesi).
"""
import argparse, collections, json, pathlib, sys, time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
from giudica_llm import costruisci, estrai  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modello', required=True, help='cartella dei pesi')
    ap.add_argument('--modo', choices=('chat', 'thinking'), default='thinking')
    ap.add_argument('--uscita', required=True)
    ap.add_argument('--memoria', type=float, default=0.85)
    ap.add_argument('--max-righe', type=int, default=0)
    a = ap.parse_args()

    sys.path.insert(0, str(pathlib.Path(a.modello)/'encoding'))
    from encoding_dsv4 import encode_messages

    righe = [json.loads(x) for x in open(QUI/'training'/'urgenda_decisione_prova_corrette_larghe.jsonl', encoding='utf-8') if x.strip()]
    if a.max_righe:
        righe = righe[:a.max_righe]
    print(f'righe {len(righe)} ({sum(r["etichetta"] for r in righe)} vere), modo {a.modo}', flush=True)

    from vllm import LLM, SamplingParams
    t0 = time.time()
    llm = LLM(model=a.modello, max_model_len=32768, gpu_memory_utilization=a.memoria,
              trust_remote_code=True, tokenizer_mode='auto')
    print(f'caricato in {time.time()-t0:.0f}s', flush=True)
    prompts = [encode_messages([{'role': 'user', 'content': costruisci(r)}], thinking_mode=a.modo) for r in righe]
    sp = SamplingParams(temperature=0.0 if a.modo == 'chat' else 0.6, top_p=1.0 if a.modo == 'chat' else 0.95,
                        max_tokens=1200 if a.modo == 'chat' else 8000, seed=20260923)
    t0 = time.time()
    out = llm.generate(prompts, sp)
    dt = time.time() - t0
    fuori = []
    for r, o in zip(righe, out):
        testo = o.outputs[0].text
        ragionamento, _, risposta = testo.rpartition('</think>') if '</think>' in testo else ('', '', testo)
        g = estrai(risposta)
        fuori.append({'id': r['id'], 'etichetta': r['etichetta'], 'sonda_titolo': r.get('sonda_titolo'),
                      'case_id': r.get('case_id'), 'llm': g, 'ragionamento': ragionamento.strip(),
                      'token': len(o.outputs[0].token_ids)})
    pathlib.Path(a.uscita).write_text(json.dumps(fuori, ensure_ascii=False, indent=1), encoding='utf-8')
    tok = sum(x['token'] for x in fuori)
    print(f'generazione {dt:.0f}s, {tok} token in uscita ({tok/dt:.0f}/s in parallelo, {tok/len(fuori):.0f} per riga)')
    print('esiti:', collections.Counter(x['llm'].get('esito') for x in fuori).most_common())
    print('scritto', a.uscita)


if __name__ == '__main__':
    main()
