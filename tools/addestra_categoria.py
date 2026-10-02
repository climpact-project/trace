"""COMPITO A — LA CATEGORIA DEL CODEBOOK. LoRA sullo stesso encoder, testa a piu' classi.

   COSA IMPARA. Dato un passaggio in cui il caso e' citato, che lavoro fa quella
   citazione nel testo: menzione in catena, descrittiva, sostanziale,
   distinguente. Le categorie sono quelle del codebook `0.2-pilot`, esclusive.

   SOLO RETE LESSICALE. La categoria sulle righe semantiche era un
   fraintendimento del compito e il 22/09/2026 e' stata rimossa dalle 81 righe
   che l'avevano: non e' un dato e non entra qui.

   DUE CATEGORIE RESTANO FUORI, e va detto nell'articolo invece di nasconderlo.
   `critica` ha due esempi in addestramento: due esempi non insegnano una
   classe, la fanno solo sembrare imparata. `implicita` ne ha uno solo, ed e'
   per giunta un residuo: implicita significa che il nome non c'e', e questa e'
   la rete che il nome lo trova.

   STESSO ENCODER DEL RIORDINATORE. `bge-reranker-v2-m3` e' un XLM-RoBERTa
   large con una testa da un'uscita; qui si prende lo stesso corpo e gli si
   mette una testa a quattro uscite. E' lo stesso modello che ha letto i
   passaggi in prima battuta: cambiarlo renderebbe i due compiti non
   confrontabili fra loro.

   IL CASO E' MASCHERATO. Senza mascheramento il modello imparerebbe a
   riconoscere la forma del nome invece del lavoro argomentativo.

   L'INGRESSO E' IL PASSAGGIO, NON LA PAGINA. Primo tentativo, 22/09/2026:
   data in pasto la finestra di pagina, come nel compito B. Non ha imparato
   niente — accuratezza 0,39-0,44 contro lo 0,427 di chi risponde sempre la
   classe piu' frequente, kappa ~0, `distinguente` mai predetta. La causa non
   era la taglia del campione: nella finestra il segnaposto del caso compare
   2 volte in mediana e fino a 16, e nel 73% dei casi piu' di una. Al modello
   si chiedeva che lavoro facesse «la» citazione senza dirgli QUALE, mentre
   l'umano aveva davanti il passaggio preciso. Dare la pagina intera qui non
   e' dare piu' contesto: e' togliere il puntamento. Nel passaggio da 460
   caratteri il segnaposto compare una volta sola e non manca mai.
   Il compito B non ha questo problema perche' li' la sonda dice al modello
   che cosa cercare; qui non c'e' nessuna sonda.
"""
import argparse, json, pathlib, collections
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent
MODELLO = 'BAAI/bge-reranker-v2-m3'
CLASSI = ['sostanziale', 'menzione_in_catena', 'descrittiva', 'distinguente']


def carica(nome):
    p = QUI/'training'/f'urgenda_categoria_{nome}.jsonl'
    righe = [json.loads(r) for r in p.read_text(encoding='utf-8').splitlines() if r.strip()]
    return [x for x in righe if x['categoria'] in CLASSI]


def rapporto(y, p):
    """Accuratezza, kappa di Cohen contro l'umano, e F1 per classe.

    La kappa e' la misura che va confrontata con l'accordo FRA UMANI, quando
    lo avremo: dice quanto la macchina concorda al netto del caso. L'accuratezza
    nuda su classi sbilanciate premia chi risponde sempre la classe piu'
    frequente."""
    y, p = np.asarray(y), np.asarray(p)
    acc = float((y == p).mean())
    n = len(y)
    pe = sum((y == c).mean()*(p == c).mean() for c in range(len(CLASSI)))
    kappa = (acc - pe)/(1 - pe) if pe < 1 else float('nan')
    righe = [f'    accuratezza {acc:.3f}   kappa {kappa:.3f}   '
             f'(rispondere sempre la classe piu frequente: {max(collections.Counter(y).values())/n:.3f})']
    for i, c in enumerate(CLASSI):
        vp = int(((p == i) & (y == i)).sum()); fp = int(((p == i) & (y != i)).sum()); fn = int(((p != i) & (y == i)).sum())
        prec = vp/(vp+fp) if vp+fp else 0.0
        ric = vp/(vp+fn) if vp+fn else 0.0
        f1 = 2*prec*ric/(prec+ric) if prec+ric else 0.0
        righe.append(f'      {c:20s} n={int((y==i).sum()):3d}  prec {prec:.2f}  ric {ric:.2f}  F1 {f1:.2f}')
    return '\n'.join(righe)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epoche', type=int, default=6)
    ap.add_argument('--lr', type=float, default=2e-4)
    ap.add_argument('--rango', type=int, default=16)
    ap.add_argument('--maxlen', type=int, default=2304)
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--seme', type=int, default=20260922)
    ap.add_argument('--ingresso', default='passaggio', choices=['passaggio', 'finestra'])
    a = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    from peft import LoraConfig, get_peft_model
    dev = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')

    tr, te = carica('addestramento'), carica('prova')
    print(f'dispositivo {dev}   ingresso «{a.ingresso}»   addestramento {len(tr)}   prova {len(te)}', flush=True)
    print('  addestramento:', collections.Counter(x['categoria'] for x in tr).most_common(), flush=True)
    print('  prova        :', collections.Counter(x['categoria'] for x in te).most_common(), flush=True)

    tok = AutoTokenizer.from_pretrained(MODELLO)
    m = AutoModelForSequenceClassification.from_pretrained(
        MODELLO, num_labels=len(CLASSI), ignore_mismatched_sizes=True)
    cfg = LoraConfig(task_type='SEQ_CLS', r=a.rango, lora_alpha=a.rango*2, lora_dropout=0.1,
                     target_modules=['query', 'key', 'value', 'dense'])
    # Stessa ragione del compito B: a 2304 token l'attenzione costa quanto il
    # quadrato della lunghezza e le attivazioni saturano gli 80 GiB. Con il
    # checkpoint del gradiente si ricalcolano invece di tenerle.
    m.gradient_checkpointing_enable()
    m.config.use_cache = False
    m = get_peft_model(m, cfg).to(dev)
    m.enable_input_require_grads()
    m.print_trainable_parameters()

    y_te = [CLASSI.index(x['categoria']) for x in te]
    opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=a.lr)
    perdita = torch.nn.CrossEntropyLoss()
    rnd = np.random.default_rng(a.seme)

    def prevedi(dati):
        m.eval(); out = []
        with torch.no_grad():
            for i in range(0, len(dati), a.batch):
                b = dati[i:i+a.batch]
                enc = tok([x[a.ingresso] for x in b], padding=True, truncation=True,
                          max_length=a.maxlen, return_tensors='pt').to(dev)
                with torch.autocast('cuda', dtype=torch.bfloat16, enabled=(dev == 'cuda')):
                    lo = m(**enc).logits
                out += lo.float().argmax(-1).cpu().tolist()
        return out

    print('\n══ prima di addestrare (testa a caso) ══')
    print(rapporto(y_te, prevedi(te)), flush=True)

    for ep in range(a.epoche):
        m.train()
        idx = rnd.permutation(len(tr)); somma = 0.0; n = 0
        for i in range(0, len(idx), a.batch):
            b = [tr[j] for j in idx[i:i+a.batch]]
            enc = tok([x[a.ingresso] for x in b], padding=True, truncation=True,
                      max_length=a.maxlen, return_tensors='pt').to(dev)
            et = torch.tensor([CLASSI.index(x['categoria']) for x in b], device=dev)
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=(dev == 'cuda')):
                lo = m(**enc).logits
            l = perdita(lo.float(), et)
            l.backward(); opt.step(); opt.zero_grad()
            somma += l.item()*len(b); n += len(b)
        print(f'\n  epoca {ep+1}/{a.epoche}  perdita {somma/n:.4f}', flush=True)
        print(rapporto(y_te, prevedi(te)), flush=True)

    p = prevedi(te)
    m.save_pretrained(QUI/'training'/'lora_categoria')
    (QUI/'training'/'esiti_categoria.json').write_text(json.dumps({
        'modello': MODELLO, 'classi': CLASSI, 'epoche': a.epoche, 'lr': a.lr,
        'rango': a.rango, 'maxlen': a.maxlen, 'seme': a.seme,
        'previsioni': {x['id']: CLASSI[q] for x, q in zip(te, p)},
        'vere': {x['id']: x['categoria'] for x in te}}, indent=1), encoding='utf-8')
    print('\nadattatore salvato in training/lora_categoria', flush=True)


if __name__ == '__main__':
    main()
