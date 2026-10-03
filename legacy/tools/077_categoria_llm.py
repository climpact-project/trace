"""LA CATEGORIA DEL CODEBOOK DATA DA UN LETTORE — DeepSeek V4 Flash.

   PERCHE'. Sulle righe lessicali (il caso e' nominato) il gruppo assegna una
   delle categorie del codebook: sostanziale, descrittiva, menzione in catena,
   distinguente, critica. Il modello addestrato per questo (LoRA, §58) arriva
   a 0,527 di accuratezza e kappa 0,224, appena sopra il dire sempre la classe
   piu' frequente (0,427). Qui si prova se un lettore che ha davanti le
   DEFINIZIONI del codebook (`codebook/citazioni.yaml`, versione 0.2-pilot) e
   la pagina fa meglio, sulle stesse 111 righe di prova.

   DUE VARIANTI, nello stesso giro:
     zero   solo le definizioni del codebook;
     esempi le definizioni piu' due passaggi per categoria presi dalle righe di
            ADDESTRAMENTO con la categoria data dal gruppo (mai dalla prova).

   Il nome del caso non e' mascherato: la maschera serviva a non far imparare
   il nome al LoRA; qui il lettore deve sapere quale citazione classificare.
"""
import argparse, collections, json, pathlib, random, re, sys, time
import yaml

QUI = pathlib.Path(__file__).resolve().parent.parent
CATEGORIE = ['sostanziale', 'descrittiva', 'menzione_in_catena', 'distinguente', 'critica']


def smaschera(t):
    return (t or '').replace('⟦CASO_CITATO⟧', 'Urgenda')


def definizioni():
    cb = yaml.safe_load((QUI/'codebook'/'citazioni.yaml').read_text(encoding='utf-8'))
    righe = []
    for c in cb['tipo_citazione']:
        if c['codice'] not in CATEGORIE:
            continue
        righe.append(f'- "{c["codice"]}" ({c["nome"]}): {" ".join(c["definizione"].split())} '
                     f'Indizi tipici: {"; ".join(c.get("indizi") or [])}.')
    return '\n'.join(righe)


def prompt(r, defs, esempi=''):
    return f"""Sei un giurista che codifica le citazioni di un precedente giudiziario secondo un codebook.

Il precedente citato e' Urgenda Foundation c. Paesi Bassi (Tribunale dell'Aja 2015, Corte d'appello 2018, Hoge Raad 2019).

CATEGORIE DEL CODEBOOK (esclusive: una sola per passaggio):
{defs}
{esempi}
PAGINA IN CUI COMPARE LA CITAZIONE (contesto):
---
{smaschera(r['finestra'])[:12000]}
---

PASSAGGIO DA CLASSIFICARE (e' dentro la pagina qui sopra):
---
{smaschera(r['passaggio'])}
---

Che lavoro fa la citazione di Urgenda in questo passaggio? Rispondi SOLO con un oggetto JSON:
{{"motivo": "una frase", "categoria": "una delle cinque sigle"}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modello', required=True)
    ap.add_argument('--modo', choices=('chat', 'thinking'), default='thinking')
    ap.add_argument('--uscita', required=True)
    ap.add_argument('--memoria', type=float, default=0.85)
    a = ap.parse_args()
    sys.path.insert(0, str(pathlib.Path(a.modello)/'encoding'))
    from encoding_dsv4 import encode_messages

    carica = lambda p: [json.loads(x) for x in open(QUI/'training'/f'urgenda_categoria_{p}.jsonl', encoding='utf-8') if x.strip()]
    tr, te = carica('addestramento'), carica('prova')
    defs = definizioni()
    rnd = random.Random(20260923)
    es = []
    for c in CATEGORIE:
        cand = [x for x in tr if x['categoria'] == c]
        for x in rnd.sample(cand, min(2, len(cand))):
            es.append(f'«{smaschera(x["passaggio"]).strip()}» -> {c}')
    esempi = '\nESEMPI GIA\' CODIFICATI DAL GRUPPO DI RICERCA:\n' + '\n'.join(es) + '\n'
    print(f'prova {len(te)}: {collections.Counter(x["categoria"] for x in te)}', flush=True)

    from vllm import LLM, SamplingParams
    llm = LLM(model=a.modello, max_model_len=32768, gpu_memory_utilization=a.memoria, trust_remote_code=True)
    varianti = {'zero': '', 'esempi': esempi}
    pr = [encode_messages([{'role': 'user', 'content': prompt(r, defs, e)}], thinking_mode=a.modo)
          for e in varianti.values() for r in te]
    sp = SamplingParams(temperature=0.0 if a.modo == 'chat' else 0.6, top_p=1.0 if a.modo == 'chat' else 0.95,
                        max_tokens=800 if a.modo == 'chat' else 6000, seed=20260923)
    t0 = time.time()
    out = llm.generate(pr, sp)
    print(f'generazione {time.time()-t0:.0f}s', flush=True)
    esiti = {}
    for i, v in enumerate(varianti):
        righe = []
        for r, o in zip(te, out[i*len(te):(i+1)*len(te)]):
            t = o.outputs[0].text.rpartition('</think>')[2] if '</think>' in o.outputs[0].text else o.outputs[0].text
            m = re.search(r'"categoria"\s*:\s*"([a-z_]+)"', t)
            righe.append({'id': r['id'], 'umano': r['categoria'], 'llm': m.group(1) if m else 'ILLEGGIBILE',
                          'motivo': (re.search(r'"motivo"\s*:\s*"([^"]*)"', t) or [None, ''])[1]})
        y, p = [x['umano'] for x in righe], [x['llm'] for x in righe]
        acc = sum(a_ == b for a_, b in zip(y, p)) / len(y)
        k = kappa(y, p)
        print(f'\n{v}: accuratezza {acc:.3f}  kappa {k:.3f}   (LoRA 0.527 / 0.224, classe piu frequente 0.427)')
        print('  confusione (umano -> lettore):')
        cm = collections.Counter(zip(y, p))
        for c in CATEGORIE:
            print(f'    {c:20s}', {q: n for (u, q), n in cm.items() if u == c})
        esiti[v] = {'accuratezza': acc, 'kappa': k, 'righe': righe}
    pathlib.Path(a.uscita).write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding='utf-8')


def kappa(y, p):
    n = len(y); po = sum(a == b for a, b in zip(y, p)) / n
    cy, cp = collections.Counter(y), collections.Counter(p)
    pe = sum(cy[c] * cp[c] for c in set(y) | set(p)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else float('nan')


if __name__ == '__main__':
    main()
