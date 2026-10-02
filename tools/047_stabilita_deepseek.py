"""LA STABILITA' DI DEEPSEEK (02/10/2026): QUANTE VOLTE LA MACCHINA RIDICE LA STESSA COSA.

   Perche'. Le proposte in piattaforma sono UNA lettura (due letture interne, poi composte). Per l'articolo serve
   sapere quanto sono stabili: rilette da capo, con le stesse istruzioni e gli stessi testi, danno lo stesso
   risultato? E' il tetto di quanto ci si puo' aspettare dall'accordo fra macchina e persone.

   Come. Un campione fisso per caso (100 righe, seme 20261002; Urgenda 58, tutte quelle della sua lettura L04 «nuove»),
   riletto sulle GPU con le istruzioni in uso: principi (L04, `032_leggi_l04.py --etichetta stab`) e tipo
   (L03, `024_classifica_lessicali.py --etichetta stab`). Si confronta con la lettura in piattaforma:
     - principi: insieme dei principi di ciascuna lettura (senza «nessuno» e «altro»); stesso insieme fra giri
       (lettura 1 con lettura 1), accordo di Jaccard medio, e per confronto l'accordo FRA le due letture dello stesso
       giro (quello che la macchina gia' misura su se stessa);
     - tipo: lettura 1 con lettura 1, quota uguale e kappa di Cohen; di nuovo con l'accordo interno come riferimento.
   Scrive training/confronto_sonde/stabilita_deepseek.json.

   Uso:  .venv/bin/python tools/047_stabilita_deepseek.py
"""
import collections, json, pathlib
QUI = pathlib.Path(__file__).resolve().parent.parent
P, T = QUI/'training'/'principi', QUI/'training'
L04 = {'urgenda': 'l04nuove', 'neubauer': 'l04P05', 'future-generations': 'l04P05',
       'klimaseniorinnen': 'l04nuove', 'cig-parere-clima': 'l04nuove', 'idh-oc-32-25': 'l04nuove'}
TIPO = {'urgenda': 'v10'}                    # la lettura del tipo delle righe del campione: per Urgenda la v10 (le righe nuove), gli altri la prima


def principi(lettura):
    if not isinstance(lettura, dict):
        return None
    v = lettura.get('principi')
    if isinstance(v, str):
        try:
            v = json.loads(v.replace("'", '"'))
        except ValueError:
            v = [v]
    return frozenset(str(p).split('.')[-1] for p in (v or []) if str(p).split('.')[-1] not in ('nessuno', 'altro', ''))


def tipo(lettura):
    return lettura.get('tipo_citazione') if isinstance(lettura, dict) else None


def carica(f):
    return {json.loads(l)['id']: json.loads(l) for l in open(f, encoding='utf-8')} if f.exists() else {}


def jaccard(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def kappa(coppie):
    n = len(coppie)
    if not n:
        return None
    po = sum(a == b for a, b in coppie) / n
    ca, cb = collections.Counter(a for a, _ in coppie), collections.Counter(b for _, b in coppie)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


def main():
    out = {}
    for caso, et in L04.items():
        prima, dopo = carica(P/f'{caso}_ripresa_deepseek_{et}.jsonl'), carica(P/f'{caso}_ripresa_deepseek_stab.jsonl')
        uguali = jac = n = interne = n_int = 0
        for rid, d in dopo.items():
            p = prima.get(rid)
            if not p:
                continue
            a, b = principi((p.get('letture') or [None])[0]), principi((d.get('letture') or [None])[0])
            if a is None or b is None:
                continue
            n += 1; uguali += a == b; jac += jaccard(a, b)
            l = p.get('letture') or []
            if len(l) > 1 and principi(l[1]) is not None:
                n_int += 1; interne += principi(l[0]) == principi(l[1])
        tp, td = carica(T/f"lessicali_{caso}_deepseek{'_' + TIPO[caso] if caso in TIPO else ''}.jsonl"), carica(T/f'lessicali_{caso}_deepseek_stab.jsonl')
        cp, ci = [], []
        for rid, d in td.items():
            p = tp.get(rid)
            if not p:
                continue
            a, b = tipo((p.get('letture') or [None])[0]), tipo((d.get('letture') or [None])[0])
            if a and b:
                cp.append((a, b))
            l = p.get('letture') or []
            if len(l) > 1 and tipo(l[0]) and tipo(l[1]):
                ci.append((tipo(l[0]), tipo(l[1])))
        out[caso] = {
            'principi_righe': n, 'principi_stesso_insieme_fra_giri': round(uguali / n, 3) if n else None,
            'principi_jaccard_fra_giri': round(jac / n, 3) if n else None,
            'principi_stesso_insieme_fra_letture_dello_stesso_giro': round(interne / n_int, 3) if n_int else None,
            'tipo_righe': len(cp), 'tipo_uguale_fra_giri': round(sum(a == b for a, b in cp) / len(cp), 3) if cp else None,
            'tipo_kappa_fra_giri': kappa(cp),
            'tipo_uguale_fra_letture_dello_stesso_giro': round(sum(a == b for a, b in ci) / len(ci), 3) if ci else None,
            'tipo_kappa_fra_letture_dello_stesso_giro': kappa(ci)}
        print(caso, out[caso])
    (QUI/'training'/'confronto_sonde').mkdir(exist_ok=True)
    json.dump(out, open(QUI/'training'/'confronto_sonde'/'stabilita_deepseek.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
