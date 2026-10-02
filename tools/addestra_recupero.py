"""LA RETE SEMANTICA — LoRA su `intfloat/multilingual-e5-large`.

   E' IL MODELLO CHE SETACCIA, non quello che riordina. Trasforma ogni testo in
   un punto a 1024 dimensioni; la ricerca e' il confronto fra il punto della
   sonda e i punti dei 1.210.717 frammenti. Addestrarlo e' un lavoro diverso dal
   riordinatore: quello legge due testi insieme e risponde si'/no, questo deve
   COLLOCARE ogni testo nello spazio senza sapere che cosa gli verra' chiesto.

   CONSEGUENZA PRATICA, E VA DETTA PRIMA DI COMINCIARE. Se il modo di fare i
   punti cambia, i punti gia' calcolati non valgono piu' e l'indice va rifatto
   per intero. Percio' si procede in due tempi: qui si addestra e si misura
   sulle sole righe giudicate (minuti); l'indice si rifa' dopo, e solo se la
   misura lo giustifica.

   COSA IMPARA, e perche' i nostri dati sono adatti. Per ogni sonda ci sono
   passaggi che un umano ha CONFERMATO e passaggi che ha SCARTATO. Gli scartati
   non sono rumore preso a caso: sono frammenti che il modello aveva messo in
   cima e una persona ha bocciato. In gergo sono «negativi difficili», e sono
   il materiale piu' costoso da procurarsi in questo tipo di addestramento.
   Noi ne abbiamo 193 in addestramento, gia' pagati con lavoro umano.

   LA PERDITA. Per ogni sonda si chiede che i passaggi confermati stiano PIU'
   VICINI dei bocciati. Non si chiede un punteggio assoluto — che al modello
   non serve e che il §55 ha mostrato essere compresso in una banda strettissima
   su un corpus monotematico — si chiede solo l'ORDINE fra vero e falso.

   IL FRAMMENTO, NON LA FINESTRA. L'indice e' costruito sui frammenti (mediana
   1.290 caratteri, 512 token). Addestrare sulla finestra di pagina e poi
   indicizzare i frammenti insegnerebbe una cosa e ne userebbe un'altra.

   IL PREFISSO. Il manifesto dell'indice dichiara `passage: ` su ENTRAMBI i
   lati, domanda compresa: scelta misurata il 31/07/2026 e non riscritta qui.
"""
import argparse, json, pathlib, collections
import numpy as np

QUI = pathlib.Path(__file__).resolve().parent.parent
MODELLO = 'intfloat/multilingual-e5-large'
PREFISSO = 'passage: '          # da index/manifesto.json, entrambi i lati


def carica(nome):
    p = QUI/'training'/f'urgenda_decisione_{nome}.jsonl'
    righe = [json.loads(r) for r in p.read_text(encoding='utf-8').splitlines() if r.strip()]
    return [x for x in righe if x['frammento']]


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float)
    o = np.argsort(s); r = np.empty(len(s), float); r[o] = np.arange(1, len(s)+1)
    for v in np.unique(s):
        m = s == v
        if m.sum() > 1:
            r[m] = r[m].mean()
    p, n = y.sum(), len(y)-y.sum()
    return float((r[y == 1].sum() - p*(p+1)/2)/(p*n)) if p and n else float('nan')


def precisione_media(y, s):
    o = np.argsort(-np.asarray(s, dtype=float)); y = np.asarray(y)[o]
    if y.sum() == 0:
        return float('nan')
    return float(((np.cumsum(y)/np.arange(1, len(y)+1))*y).sum()/y.sum())


def riassunto(nome, y, s):
    y = np.asarray(y); s = np.asarray(s, dtype=float)
    out = [f'  {nome:42s} AUC {auc(y,s):.3f}   AP {precisione_media(y,s):.3f}   base {y.mean():.3f}']
    for k in (20, 40):
        if k <= len(y):
            t = np.argsort(-s)[:k]
            out.append(f'      prime {k:3d} righe: {int(y[t].sum()):3d} vere  ({100*y[t].mean():.0f}%)')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epoche', type=int, default=6)
    ap.add_argument('--lr', type=float, default=1e-4)
    ap.add_argument('--rango', type=int, default=16)
    ap.add_argument('--maxlen', type=int, default=512)
    ap.add_argument('--temperatura', type=float, default=0.05)
    ap.add_argument('--seme', type=int, default=20260922)
    ap.add_argument('--solo-paragoni', action='store_true')
    ap.add_argument('--moduli', default='query,key,value,dense')
    ap.add_argument('--ancora', type=float, default=0.0)
    ap.add_argument('--solo-domanda', action='store_true',
                    help='adatta SOLO il lato della sonda: i documenti restano '
                         'codificati dal modello originale, quindi l indice da '
                         '1.210.717 punti NON va rifatto.')
    a = ap.parse_args()

    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import LoraConfig, get_peft_model
    dev = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
    torch.manual_seed(a.seme)

    tr, te = carica('addestramento'), carica('prova')
    print(f'dispositivo {dev}   addestramento {len(tr)} ({sum(x["etichetta"] for x in tr)} positive)   '
          f'prova {len(te)} ({sum(x["etichetta"] for x in te)} positive)', flush=True)
    y_te = [x['etichetta'] for x in te]

    tok = AutoTokenizer.from_pretrained(MODELLO)

    def vettori(modello, testi, batch=16):
        fuori = []
        modello.eval()
        with torch.no_grad():
            for i in range(0, len(testi), batch):
                enc = tok([PREFISSO+t for t in testi[i:i+batch]], padding=True, truncation=True,
                          max_length=a.maxlen, return_tensors='pt').to(dev)
                with torch.autocast('cuda', dtype=torch.bfloat16, enabled=(dev == 'cuda')):
                    h = modello(**enc).last_hidden_state
                m = enc['attention_mask'].unsqueeze(-1).float()
                v = (h.float()*m).sum(1)/m.sum(1)          # media pesata, come e5
                fuori.append(F.normalize(v, dim=-1).cpu())
        return torch.cat(fuori)

    def punteggia(modello, doc_base=None):
        vs = vettori(modello, [x['sonda_testo'] for x in te])
        vp = vettori(doc_base if doc_base is not None else modello, [x['frammento'] for x in te])
        return (vs*vp).sum(-1).tolist()

    print('\n══ TERMINI DI PARAGONE ══', flush=True)
    print(riassunto('1. punteggio archiviato (luglio 2026)', y_te, [x['punteggio'] for x in te]), flush=True)
    base = AutoModel.from_pretrained(MODELLO).to(dev)
    s0 = punteggia(base)
    print(riassunto('2. non addestrato, ricalcolato adesso', y_te, s0), flush=True)
    d = np.abs(np.array(s0)-np.array([x['punteggio'] for x in te]))
    print(f'      verifica ricostruzione: scarto medio {d.mean():.4f}, massimo {d.max():.4f}', flush=True)
    if a.solo_paragoni:
        return

    print('\n══ ADDESTRAMENTO LoRA ══', flush=True)
    cfg = LoraConfig(r=a.rango, lora_alpha=a.rango*2, lora_dropout=0.1,
                     target_modules=a.moduli.split(','))
    m = get_peft_model(AutoModel.from_pretrained(MODELLO), cfg).to(dev)
    m.print_trainable_parameters()

    # Raggruppo per sonda: ogni gruppo ha i suoi confermati e i suoi bocciati.
    gruppi = collections.defaultdict(lambda: {'si': [], 'no': []})
    for x in tr:
        gruppi[x['sonda_titolo']]['si' if x['etichetta'] else 'no'].append(x['frammento'])
    gruppi = {k: v for k, v in gruppi.items() if v['si'] and v['no']}
    print(f'  sonde utilizzabili (con almeno un confermato e un bocciato): {len(gruppi)}', flush=True)
    testi_sonda = {x['sonda_titolo']: x['sonda_testo'] for x in tr}

    def _media(enc, h):
        mk = enc['attention_mask'].unsqueeze(-1).float()
        return F.normalize((h.float()*mk).sum(1)/mk.sum(1), dim=-1)

    def codifica(testi, adattato=True):
        enc = tok([PREFISSO+t for t in testi], padding=True, truncation=True,
                  max_length=a.maxlen, return_tensors='pt').to(dev)
        if adattato:
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=(dev == 'cuda')):
                h = m(**enc).last_hidden_state
            return _media(enc, h)
        # documenti col modello ORIGINALE: e' cosi' che stanno nell indice
        with torch.no_grad(), m.disable_adapter():
            with torch.autocast('cuda', dtype=torch.bfloat16, enabled=(dev == 'cuda')):
                h = m(**enc).last_hidden_state
            return _media(enc, h).detach()

    opt = torch.optim.AdamW([p for p in m.parameters() if p.requires_grad], lr=a.lr)
    rnd = np.random.default_rng(a.seme)
    migliore = 0.0
    MAX_NEG = 12
    for ep in range(a.epoche):
        m.train(); somma = 0.0; n = 0
        chiavi = list(gruppi); rnd.shuffle(chiavi)
        for k in chiavi:
            si, no = gruppi[k]['si'], gruppi[k]['no']
            pos = si[rnd.integers(len(si))]
            neg = list(rnd.choice(no, size=min(MAX_NEG, len(no)), replace=False))
            vq = codifica([testi_sonda[k]])
            vd = codifica([pos]+neg, adattato=not a.solo_domanda)
            log = (vq @ vd.T).reshape(-1)/a.temperatura
            l = F.cross_entropy(log.unsqueeze(0), torch.tensor([0], device=dev))
            if a.ancora > 0:
                # Tiene i vettori vicini a quelli del modello di partenza: la
                # perdita contrastiva da sola, con dieci sole domande, e' libera
                # di stravolgere lo spazio che serve agli altri 1,2 milioni.
                with torch.no_grad():
                    with m.disable_adapter():
                        vq0 = codifica([testi_sonda[k]]).detach()
                        vd0 = codifica([pos]+neg).detach()
                l = l + a.ancora*((1-(vq*vq0).sum(-1)).mean() + (1-(vd*vd0).sum(-1)).mean())
            l.backward(); opt.step(); opt.zero_grad()
            somma += l.item(); n += 1
        s = punteggia(m, base if a.solo_domanda else None)
        print(f'\n  epoca {ep+1}/{a.epoche}  perdita {somma/n:.4f}', flush=True)
        print(riassunto(f'   dopo epoca {ep+1}', y_te, s), flush=True)
        migliore = max(migliore, auc(y_te, s))

    m.save_pretrained(QUI/'training'/f'lora_recupero_{a.seme}')
    (QUI/'training'/f'esiti_recupero_{a.seme}.json').write_text(json.dumps({
        'modello': MODELLO, 'prefisso': PREFISSO, 'seme': a.seme, 'epoche': a.epoche,
        'lr': a.lr, 'rango': a.rango, 'maxlen': a.maxlen, 'temperatura': a.temperatura,
        'auc_archiviato': auc(y_te, [x['punteggio'] for x in te]),
        'auc_non_addestrato': auc(y_te, s0), 'auc_addestrato': auc(y_te, s),
        'punteggi_prova': {x['id']: v for x, v in zip(te, s)}}, indent=1), encoding='utf-8')
    print(f'\nMIGLIORE {auc(y_te,[x["punteggio"] for x in te]):.3f} archiviato -> {migliore:.3f} addestrato   (lr {a.lr} rango {a.rango} moduli {a.moduli} ancora {a.ancora} temp {a.temperatura})'.format(a=a), flush=True)


if __name__ == '__main__':
    main()
