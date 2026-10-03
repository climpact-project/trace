"""IL PUNTO DENTRO LA PAGINA — quale frammento indicare al validatore.

   PERCHE' (catalogo parziale, 25/09/2026). Cercare per pagine trova le stesse
   riprese vere che cercare per frammenti (18 contro 17 su 32 ai primi 500
   posti), ma dentro la pagina vera il frammento migliore secondo Qwen e'
   quello giudicato solo in 3 pagine su 11. Al validatore va indicato il punto,
   non la pagina intera: serve un secondo passaggio che lo trovi.

   LA PROVA. Per OGNI ripresa vera delle righe di prova (32, non solo quelle
   trovate: il puntamento si misura a parte dalla ricerca), si prendono i
   frammenti della sua pagina e si chiede a ciascun metodo quale sia il
   migliore. Riuscita = il frammento scelto contiene il punto su cui il
   validatore ha giudicato. Si riportano primo posto e primi due.
     - caso: un frammento a sorte (la soglia sotto cui un metodo non serve);
     - Qwen embedding, domanda addestrata (quello di oggi nel catalogo);
     - e5 (il sistema di luglio);
     - riordinatore Qwen3-Reranker-4B addestrato (tre semi, media), che e'
       il secondo passaggio gia' previsto nella catena.

   Uso (GPU):  python3 tools/110_puntamento.py
"""
import collections, json, pathlib, random, sys
import numpy as np
import torch

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
T = QUI/'training'


def main():
    import torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModel
    from peft import PeftModel
    _m_catalogo_parziale = __import__('076_catalogo_parziale')
    ISTR_Q = _m_catalogo_parziale.ISTR
    _m_prova_riordinatori = __import__('027_prova_riordinatori')
    QwenRiordinatore = _m_prova_riordinatori.QwenRiordinatore
    ISTR = _m_prova_riordinatori.ISTR
    c = json.loads((T/'catalogo_parziale.json').read_text(encoding='utf-8'))
    Fr = c['frammenti']
    vere = [r for r in c['righe'] if r['parte'] == 'prova' and r['etichetta']]
    per_pagina = collections.defaultdict(list)
    for f in Fr:
        per_pagina[(f['doc'], f['pagina'])].append(f)
    casi = []
    for r in vere:
        fs = per_pagina.get((r['doc'], r['pagina']), [])
        ok = [f['da'] <= r['char'] <= f['a'] for f in fs]
        if fs and any(ok):
            casi.append((r, fs, ok))
    print(f'riprese vere {len(vere)}; con la pagina e il punto ritrovati nel catalogo {len(casi)}; '
          f'frammenti per pagina: media {np.mean([len(x[1]) for x in casi]):.1f}', flush=True)

    def esito(nome, punteggi):
        p1 = p2 = 0
        for (r, fs, ok), s in zip(casi, punteggi):
            o = np.argsort(-np.asarray(s))
            p1 += ok[o[0]]; p2 += any(ok[i] for i in o[:2])
        print(f'  {nome:48s} primo posto {p1}/{len(casi)}   primi due {p2}/{len(casi)}', flush=True)
        return {'primo': int(p1), 'primi_due': int(p2), 'n': len(casi)}

    esiti = {}
    rnd = random.Random(20260925)
    atteso1 = sum(sum(ok)/len(ok) for _, _, ok in casi)
    print(f'  {"caso (atteso)":48s} primo posto {atteso1:.1f}/{len(casi)}', flush=True)
    esiti['caso'] = {'primo_atteso': atteso1, 'n': len(casi)}

    # Qwen embedding: pagine e frammenti col modello di base, domanda con l'adattatore (§62.7)
    tok = AutoTokenizer.from_pretrained('Qwen/Qwen3-Embedding-4B', padding_side='left')
    m = AutoModel.from_pretrained('Qwen/Qwen3-Embedding-4B', torch_dtype=torch.bfloat16).cuda()
    m = PeftModel.from_pretrained(m, str(T/'lora_primo_qwen4b_solodomanda_1'/'passata_1')).eval()

    def qenc(testi, domanda):
        out = []
        import contextlib
        with torch.no_grad(), (m.disable_adapter() if not domanda else contextlib.nullcontext()):
            for i in range(0, len(testi), 16):
                t = [f'Instruct: {ISTR_Q}\nQuery:{x}' if domanda else x for x in testi[i:i+16]]
                e = tok(t, padding=True, truncation=True, max_length=2048, return_tensors='pt').to('cuda')
                h = m(**e).last_hidden_state[:, -1]
                out.append(F.normalize(h.float(), dim=-1).cpu())
        return torch.cat(out).numpy()
    esiti['qwen'] = esito('Qwen embedding, domanda addestrata',
                          [qenc([f['testo'] for f in fs], False) @ qenc([r['sonda']], True)[0] for r, fs, _ in casi])
    del m; torch.cuda.empty_cache()

    # e5
    tok = AutoTokenizer.from_pretrained('intfloat/multilingual-e5-large')
    m = AutoModel.from_pretrained('intfloat/multilingual-e5-large').cuda().eval()

    def eenc(testi):
        with torch.no_grad():
            e = tok(['passage: ' + x for x in testi], padding=True, truncation=True, max_length=512, return_tensors='pt').to('cuda')
            h = m(**e).last_hidden_state; k = e['attention_mask'].unsqueeze(-1).float()
            return F.normalize((h*k).sum(1)/k.sum(1), dim=-1).cpu().numpy()
    esiti['e5'] = esito('e5 (luglio)', [eenc([f['testo'] for f in fs]) @ eenc([r['sonda']])[0] for r, fs, _ in casi])
    del m; torch.cuda.empty_cache()

    # riordinatore addestrato, tre semi
    tutti = []
    for seme in (1, 2, 3):
        q = QwenRiordinatore('Qwen/Qwen3-Reranker-4B')
        q.m = PeftModel.from_pretrained(q.m, str(T/f'lora_qwen_rr4b_{seme}'/'passata_2'))
        tutti.append([q.punteggi([(r['sonda'], f['testo']) for f in fs], ISTR['ripresa'], 2560) for r, fs, _ in casi])
        q.libera()
    media = [np.mean([t[i] for t in tutti], 0) for i in range(len(casi))]
    esiti['riordinatore'] = esito('riordinatore Qwen3-Reranker-4B addestrato (3 semi)', media)
    (T/'esiti_puntamento.json').write_text(json.dumps(esiti, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
