"""COMPITO B — LA DECISIONE SEMANTICA. LoRA sul riordinatore che fece il lavoro.

   MODELLO. `BAAI/bge-reranker-v2-m3`, lo stesso che ha prodotto la colonna
   `punteggio_riordino` archiviata su ogni riga. Non un modello diverso: se si
   cambiasse modello, il confronto con il giudizio umano su QUESTE righe
   misurerebbe due cose insieme e non se ne potrebbe attribuire nessuna.

   TRE TERMINI DI PARAGONE, misurati prima di addestrare qualunque cosa.
     1. il punteggio ARCHIVIATO, cioe' quello che la macchina diede allora;
     2. il modello NON addestrato sul FRAMMENTO a 1024 token — le stesse
        condizioni di allora, ricostruite: deve riprodurre il punto 1. Se non
        lo riproduce, la ricostruzione e' sbagliata e ci si ferma li';
     3. il modello NON addestrato sulla FINESTRA di pagina a 2304 token — il
        nuovo ingresso, senza addestramento.
   Solo dopo il modello addestrato, sulla finestra. Cosi' l'effetto della
   finestra piu' lunga e l'effetto dell'addestramento restano separati: se si
   cambiassero tutte e due le cose insieme, un miglioramento non si saprebbe a
   chi attribuirlo.

   LA MISURA. AUC e precisione media, non l'accuratezza: le classi sono
   sbilanciate (30% di positive) e un modello che dice sempre «no» prenderebbe
   il 70% di accuratezza senza aver imparato niente. Si riporta anche la
   precisione a parita' di righe trattenute, che e' la domanda vera del
   ricercatore: se leggo le prime N, quante sono buone?
"""
import argparse, json, pathlib, time
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent
MODELLO = 'BAAI/bge-reranker-v2-m3'


SUFFISSO = ''


def carica(nome):
    p = QUI/'training'/f'urgenda_decisione_{nome}{SUFFISSO}.jsonl'
    return [json.loads(r) for r in p.read_text(encoding='utf-8').splitlines() if r.strip()]


def auc(y, s):
    """Area sotto la ROC, calcolata dai ranghi: nessuna dipendenza esterna."""
    y = np.asarray(y); s = np.asarray(s, dtype=float)
    ordine = np.argsort(s)
    ranghi = np.empty(len(s), float); ranghi[ordine] = np.arange(1, len(s)+1)
    # media dei ranghi sui pari merito
    for v in np.unique(s):
        m = s == v
        if m.sum() > 1:
            ranghi[m] = ranghi[m].mean()
    np_, nn = y.sum(), len(y) - y.sum()
    if np_ == 0 or nn == 0:
        return float('nan')
    return float((ranghi[y == 1].sum() - np_*(np_+1)/2) / (np_*nn))


def precisione_media(y, s):
    """Average precision: l'area sotto precisione-richiamo."""
    ordine = np.argsort(-np.asarray(s, dtype=float))
    y = np.asarray(y)[ordine]
    if y.sum() == 0:
        return float('nan')
    cum = np.cumsum(y)
    prec = cum/np.arange(1, len(y)+1)
    return float((prec*y).sum()/y.sum())


def riassunto(nome, y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float)
    base = y.mean()
    righe = [f'  {nome:44s} AUC {auc(y,s):.3f}   AP {precisione_media(y,s):.3f}   base {base:.3f}']
    for k in (20, 40, 60):
        if k <= len(y):
            top = np.argsort(-s)[:k]
            righe.append(f'      prime {k:3d} righe: {int(y[top].sum()):3d} vere  ({100*y[top].mean():.0f}%)')
    return '\n'.join(righe)


def punteggia(modello, tok, coppie, maxlen, dev, batch=8):
    import torch
    out = []
    modello.eval()
    with torch.no_grad():
        for i in range(0, len(coppie), batch):
            b = coppie[i:i+batch]
            enc = tok([x[0] for x in b], [x[1] for x in b], padding=True,
                      truncation=True, max_length=maxlen, return_tensors='pt').to(dev)
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=(dev == 'cuda')):
                log = modello(**enc).logits.reshape(-1)
            log = log.float()
            out += torch.sigmoid(log).cpu().tolist()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epoche', type=int, default=4)
    ap.add_argument('--lr', type=float, default=2e-4)
    ap.add_argument('--rango', type=int, default=16)
    ap.add_argument('--maxlen', type=int, default=2304)
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--accumula', type=int, default=8)
    ap.add_argument('--solo-paragoni', action='store_true')
    ap.add_argument('--seme', type=int, default=20260922)
    ap.add_argument('--etichette', default='', choices=['', '_corrette'],
                    help="'_corrette' usa le etichette con le 17 righe «citazione altrove» rimesse a falso")
    a = ap.parse_args()

    global SUFFISSO
    SUFFISSO = a.etichette
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    dev = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
    print(f'dispositivo: {dev}', flush=True)

    tr, te = carica('addestramento'), carica('prova')
    print(f'addestramento {len(tr)} righe ({sum(x["etichetta"] for x in tr)} positive)  '
          f'prova {len(te)} righe ({sum(x["etichetta"] for x in te)} positive)', flush=True)
    y_te = [x['etichetta'] for x in te]

    print('\n══ TERMINI DI PARAGONE (nessun addestramento) ══', flush=True)
    print(riassunto('1. punteggio archiviato (luglio 2026)', y_te, [x['riordino'] or 0 for x in te]), flush=True)

    tok = AutoTokenizer.from_pretrained(MODELLO)
    base = AutoModelForSequenceClassification.from_pretrained(MODELLO).to(dev)

    conf = [x for x in te if x['frammento']]
    if conf:
        t0 = time.time()
        s = punteggia(base, tok, [(x['sonda_testo'], x['frammento']) for x in conf], 1024, dev)
        print(riassunto('2. non addestrato, FRAMMENTO a 1024', [x['etichetta'] for x in conf], s), flush=True)
        vecchi = np.array([x['riordino'] or 0 for x in conf]); nuovi = np.array(s)
        print(f'      verifica ricostruzione: scarto medio dal punteggio archiviato '
              f'{np.abs(vecchi-nuovi).mean():.4f}, massimo {np.abs(vecchi-nuovi).max():.4f}  ({time.time()-t0:.0f}s)', flush=True)

    t0 = time.time()
    s_fin = punteggia(base, tok, [(x['sonda_testo'], x['finestra']) for x in te], a.maxlen, dev)
    print(riassunto(f'3. non addestrato, FINESTRA a {a.maxlen}', y_te, s_fin), flush=True)
    print(f'      ({time.time()-t0:.0f}s)', flush=True)
    if a.solo_paragoni:
        return

    print('\n══ ADDESTRAMENTO LoRA ══', flush=True)
    from peft import LoraConfig, get_peft_model
    cfg = LoraConfig(task_type='SEQ_CLS', r=a.rango, lora_alpha=a.rango*2, lora_dropout=0.1,
                     target_modules=['query', 'key', 'value', 'dense'])
    _b = AutoModelForSequenceClassification.from_pretrained(MODELLO)
    # L'attenzione costa quanto il QUADRATO della lunghezza: a 2304 token e lotto
    # 16 le attivazioni tenute per il passo all'indietro hanno saturato 79 GiB.
    # Con il checkpoint del gradiente le attivazioni intermedie NON si tengono,
    # si ricalcolano durante il passo all'indietro: un terzo di tempo in piu',
    # memoria da lineare invece che da quadratica sul numero di strati.
    _b.gradient_checkpointing_enable()
    _b.config.use_cache = False
    m = get_peft_model(_b, cfg).to(dev)
    m.enable_input_require_grads()
    m.print_trainable_parameters()

    opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=a.lr)
    perdita = torch.nn.BCEWithLogitsLoss()
    rnd = np.random.default_rng(a.seme)
    torch.manual_seed(a.seme)
    passi = 0
    for ep in range(a.epoche):
        m.train()
        idx = rnd.permutation(len(tr))
        somma, n = 0.0, 0
        opt.zero_grad()
        for j in range(0, len(idx), a.batch):
            b = [tr[i] for i in idx[j:j+a.batch]]
            enc = tok([x['sonda_testo'] for x in b], [x['finestra'] for x in b],
                      padding=True, truncation=True, max_length=a.maxlen,
                      return_tensors='pt').to(dev)
            et = torch.tensor([float(x['etichetta']) for x in b], device=dev)
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=(dev == 'cuda')):
                log = m(**enc).logits.reshape(-1)
            l = perdita(log.float(), et)
            (l/a.accumula).backward()
            somma += l.item()*len(b); n += len(b)
            if (j//a.batch + 1) % a.accumula == 0:
                opt.step(); opt.zero_grad(); passi += 1
        opt.step(); opt.zero_grad(); passi += 1
        s = punteggia(m, tok, [(x['sonda_testo'], x['finestra']) for x in te], a.maxlen, dev)
        print(f'  epoca {ep+1}/{a.epoche}  perdita {somma/n:.4f}  passi {passi}', flush=True)
        print(riassunto(f'   dopo epoca {ep+1}', y_te, s), flush=True)

    fuori = QUI/'training'/f'lora_riordino{a.etichette}_{a.seme}'
    m.save_pretrained(fuori)
    s = punteggia(m, tok, [(x['sonda_testo'], x['finestra']) for x in te], a.maxlen, dev)
    (QUI/'training'/f'esiti_riordino{a.etichette}_{a.seme}.json').write_text(json.dumps({
        'modello': MODELLO, 'epoche': a.epoche, 'lr': a.lr, 'rango': a.rango, 'maxlen': a.maxlen,
        'auc_archiviato': auc(y_te, [x['riordino'] or 0 for x in te]),
        'auc_non_addestrato_finestra': auc(y_te, s_fin),
        'auc_addestrato': auc(y_te, s), 'ap_addestrato': precisione_media(y_te, s), 'seme': a.seme,
        'punteggi_prova': {x['id']: v for x, v in zip(te, s)}}, indent=1), encoding='utf-8')
    print(f'\nadattatore salvato in {fuori}', flush=True)


if __name__ == '__main__':
    main()
