"""IL PRIMO PASSO DELLA CATENA NUOVA: cercare per pagine in tutto il corpus (§63.7, §63.14).

   Per ogni sonda semantica del caso citato: la domanda passa per il modello con l'adattatore scelto
   (media dei vettori dei tre semi), si confronta con TUTTE le pagine dell'indice del modello di base,
   e si tengono le prime K, tolti gli atti del caso citato stesso. Uscita: un CSV di candidate per il
   riordinatore e il lettore. NON pubblica niente sulla piattaforma.

   Uso (GPU): python3 tools/cerca_pagine.py --caso urgenda --modello pplx4b \
                  --adattatore 'training/lora_distilla_rrds_pplx4b_{seme}/passata_1' --k 500
   (adattatore scelto il 26/09/2026: DIARIO-ADDESTRAMENTO-CITAZIONI.md §9, documento unico §63.14)
"""
import argparse, csv, gzip, json, pathlib, sys
import numpy as np
import yaml
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
from distilla import MODELLI, indice  # noqa: E402
from addestra_primo_qwen import ISTR  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', required=True); ap.add_argument('--modello', default='pplx4b', choices=list(MODELLI))
    ap.add_argument('--adattatore', default='', help="cartella dell'adattatore, con {seme} per mediare i tre semi")
    ap.add_argument('--k', type=int, default=500)
    ap.add_argument('--posti-di', default='', help='file JSON con una lista di id di pagina: scrive a che posto stanno, e non il CSV')
    ap.add_argument('--etichetta', default='', help='suffisso del CSV di uscita')
    ap.add_argument('--alternative', action='store_true', help='cerca anche con la seconda formulazione di ogni sonda')
    ap.add_argument('--mescola', default='',
                    help="WiSE-FT: pesi dell'adattatore da provare, per esempio '0.25,0.5,0.75' (0 = modello originale)")
    ap.add_argument('--finestre', action='store_true',
                    help='cerca nelle finestre di ~1.200 caratteri (index/finestre_<modello>): la pagina vale la sua finestra migliore')
    a = ap.parse_args()
    import torch, torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import PeftModel
    NOME, POOL, PQ, CART = MODELLI[a.modello]; PQ = PQ.replace('{ISTR}', ISTR)
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{a.caso}.yaml', encoding='utf-8'))
    # Spazi normalizzati (26/09/2026): nel file del caso la sonda va a capo, nelle righe su cui gli
    # adattatori sono stati addestrati e misurati e' su una riga sola. Cosi' il testo e' identico.
    sonde = [(q['id'], ' '.join(q['testo'].split())) for q in conf.get('semantic_queries') or []]
    if a.alternative:
        # anche la seconda formulazione di ogni sonda, come la catena di luglio (id `<sonda>__alt`, come nelle
        # righe di addestramento e di prova): il 26/09 un terzo delle pagine confermate veniva da li'
        sonde += [(q['id'] + '__alt', ' '.join(q['probe_alternativa'].split()))
                  for q in conf.get('semantic_queries') or [] if q.get('probe_alternativa')]
    escludi = set(conf.get('escludi_case_id') or [])
    if a.finestre:
        # LE FINESTRE (26/09/2026): per pagina intera la frase che riprende il caso annega nel resto della
        # pagina; qui ogni finestra ha il suo vettore e la pagina prende il punteggio della migliore.
        d = QUI/'index'/f'finestre_{a.modello}'; parti = sorted(d.glob('vettori_*.npy'), key=lambda x: int(x.stem.split('_')[1]))
        Vw = np.concatenate([np.load(x) for x in parti])
        wids = sum((json.load(open(d/f"ids_{x.stem.split('_')[1]}.json")) for x in parti), [])
        pagina_di = [w.rsplit('#w', 1)[0] for w in wids]
        ids = sorted(set(pagina_di)); pos_p = {pid: i for i, pid in enumerate(ids)}
        mappa = torch.tensor([pos_p[p] for p in pagina_di], device='cuda')
        Vt = torch.from_numpy(Vw).cuda(); del Vw
        print(f'finestre {len(wids)}, pagine {len(ids)}', flush=True)
    else:
        V, ids = indice(CART); Vt = torch.from_numpy(V).cuda(); mappa = None

    def punteggi(q):
        sc = Vt @ q
        if mappa is None:
            return sc
        return torch.full((len(ids),), -9.0, device='cuda', dtype=sc.dtype).scatter_reduce(0, mappa, sc, 'amax')
    tok = AutoTokenizer.from_pretrained(NOME, padding_side='left', trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    # WiSE-FT (Wortsman et al. 2022), 26/09/2026: il modello addestrato mescolato con l'originale NEI PESI. Con
    # LoRA vuol dire scalare la correzione dell'adattatore per un peso fra 0 (originale) e 1 (addestrato).
    mescole = [float(x) for x in a.mescola.split(',')] if (a.mescola and a.adattatore) else [1.0]
    QQ = {l: [] for l in mescole}
    semi = (1, 2, 3) if '{seme}' in a.adattatore else (None,)
    for seme in semi:
        m = AutoModel.from_pretrained(NOME, torch_dtype=torch.bfloat16, trust_remote_code=True).cuda()
        strati = []
        if a.adattatore:
            from peft.tuners.lora import LoraLayer
            m = PeftModel.from_pretrained(m, str(QUI/a.adattatore.replace('{seme}', str(seme))))
            strati = [(mod, dict(mod.scaling)) for mod in m.modules() if isinstance(mod, LoraLayer)]
        m.eval()
        for l in mescole:
            for mod, orig in strati:
                mod.scaling = {k: v * l for k, v in orig.items()}
            with torch.no_grad():
                e = tok([PQ + t for _, t in sonde], padding=True, return_tensors='pt').to('cuda')
                hs = m(**e).last_hidden_state
                if POOL == 'media':
                    mk = e['attention_mask'].unsqueeze(-1).to(hs.dtype); h = (hs*mk).sum(1)/mk.sum(1)
                else:
                    h = hs[:, -1]
                QQ[l].append(F.normalize(h.float(), dim=-1))
        del m; torch.cuda.empty_cache()
    QQ = {l: F.normalize(torch.stack(v).mean(0), dim=-1).half() for l, v in QQ.items()}
    Q = QQ[mescole[0]]
    # documento -> caso: dal file delle pagine (il case_id sta nel percorso markdown/<case_id>/...)
    caso_di = {}
    with gzip.open(QUI/'index'/'pagine'/'pagine.jsonl.gz', 'rt', encoding='utf-8') as f:
        for l in f:
            x = json.loads(l); caso_di.setdefault(x['doc'], x['file'].split('/')[1])
    if a.posti_di:
      # A CHE POSTO stanno pagine note (per esempio le riprese confermate dalle persone), sonda per sonda,
      # nell'indice intero tolti gli atti del caso citato: serve a dire quale k servirebbe, invece di sceglierlo.
      cerca = json.load(open(a.posti_di)); pos = {pid: n for n, pid in enumerate(ids)}
      tenute = np.array([caso_di.get(pid.split('#')[0]) not in escludi for pid in ids])
      for l, Q in QQ.items():
        fuori = {}
        for (sid, _), q in zip(sonde, Q):
            sc = punteggi(q).float().cpu().numpy(); sc[~tenute] = -9
            ordine = np.argsort(-sc); posto = np.empty(len(ids), dtype=np.int64); posto[ordine] = np.arange(1, len(ids)+1)
            for pid in cerca:
                if pid in pos:
                    fuori.setdefault(pid, {})[sid] = int(posto[pos[pid]])
        suff = f'_m{l}' if len(QQ) > 1 or a.mescola else ''
        dove = QUI/'training'/'fase2'/f'posti_{pathlib.Path(a.posti_di).stem}{"_finestre" if a.finestre else ""}{a.etichetta}{suff}.json'
        dove.parent.mkdir(parents=True, exist_ok=True); json.dump(fuori, open(dove, 'w'), indent=1)
        print(f'posti di {len(fuori)} pagine su {len(cerca)} -> {dove}', flush=True)
      return
    uscita = QUI/'training'/f'candidati_pagine_{a.caso}_{a.modello}{a.etichetta}.csv'
    with open(uscita, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['sonda', 'posto', 'punteggio', 'pagina_id', 'document_id', 'case_id', 'pagina'])
        for (sid, _), q in zip(sonde, Q):
            sc = punteggi(q).float(); ordine = torch.argsort(sc, descending=True).cpu().numpy(); n = 0
            for i in ordine:
                doc = ids[i].split('#')[0]
                if caso_di.get(doc) in escludi:
                    continue
                n += 1; w.writerow([sid, n, round(float(sc[i]), 4), ids[i], doc, caso_di.get(doc), ids[i].split('#p')[-1]])
                if n >= a.k:
                    break
    print(f'{a.caso}: {len(sonde)} sonde, {a.k} candidate ciascuna -> {uscita}', flush=True)


if __name__ == '__main__':
    main()
