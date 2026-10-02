"""UNA PROVA NEL PORTALE (30/09/2026, il PI: «una funzione "prove" dentro corpus platform»).

   Scrive `trace_prove/<id>` (le righe da rigiudicare alla cieca, mescolate una volta) e `trace_prove/<id>/varianti/*`
   (le versioni da confrontare, riga per riga). Non tocca `corpus_rows`: i giudizi della prova vanno in
   `trace_prove/<id>/giudizi`, scritti dal portale.

   Prima prova: le righe di Urgenda gia' giudicate dal PI, rigiudicate senza proposte, contro L04, L05, L06, il
   giudizio alla cieca di Opus e il giudizio dato prima con le proposte davanti.

   Uso:  .venv/bin/python tools/crea_prova.py            anteprima
         .venv/bin/python tools/crea_prova.py --scrivi   scrive
"""
import argparse, collections, datetime, json, pathlib, random
from google.cloud import firestore
QUI = pathlib.Path(__file__).resolve().parent.parent
P = QUI/'training'/'principi'
PROVA = 'urgenda-righe-del-pi-alla-cieca'
PI = 'TKuaPxLsEobzv43Bdj7jrzyaVjs2'
# il giudizio alla cieca di Opus (30/09/2026, 120 righe): tenuto accanto alle letture, per la prova
OPUS = P/'urgenda_opus_cieco_2026-09-30.json'


def load(f):
    return {json.loads(l)['id']: json.loads(l) for l in open(f, encoding='utf-8')}


def lett(x):
    return [l for l in (x or {}).get('letture', []) if isinstance(l, dict)]


def principi(l):
    return sorted({p for p in (l.get('principi') or []) if p}) or ['nessuno']


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scrivi', action='store_true'); a = ap.parse_args()
    db = firestore.Client(project='climpact-drp')
    righe = {d.id: d.to_dict() for d in db.collection('corpus_rows').where(filter=firestore.FieldFilter('caso_citato', '==', 'urgenda')).stream()}
    mie = sorted(k for k, r in righe.items() if r.get('esito') and r.get('validato_da') == PI
                 and r.get('proposto_rete') in ('lessicale', 'entrambe'))
    random.Random(20260930).shuffle(mie)
    R = load(P/'urgenda_ripresa_righe_v2.jsonl')
    L4 = load(P/'urgenda_ripresa_deepseek.jsonl'); L5 = load(P/'urgenda_ripresa_deepseek_v2.jsonl')
    L6 = load(P/'urgenda_ripresa_deepseek_l06prova.jsonl'); opus = json.load(open(OPUS, encoding='utf-8'))
    mappa = lambda rid: set((R.get(rid) or {}).get('principi_paragrafi') or [])

    def una(L):
        return {rid: principi(lett(L[rid])[0]) for rid in mie if lett(L.get(rid))}

    def composta(L):
        out = {}
        for rid in mie:
            if lett(L.get(rid)):
                s = (set(principi(lett(L[rid])[0])) - {'nessuno'}) | mappa(rid)
                out[rid] = sorted(s) or ['nessuno']
        return out

    def due_su_quattro(L):
        out = {}
        for rid in mie:
            ls = lett(L.get(rid))
            if ls:
                c = collections.Counter(p for l in ls for p in set(principi(l)) - {'nessuno'})
                out[rid] = sorted(p for p, n in c.items() if n >= 2) or ['nessuno']
        return out

    varianti = [
        ('prima', "Giuseppe Naglieri's judgment in Uptakes", 'given with the proposals in front of him',
         {rid: sorted(righe[rid].get('validato_principi') or []) or ['nessuno'] for rid in mie if righe[rid].get('esito') != 'scartata'}),
        ('vista', 'The proposal he saw', 'L04 composed with the paragraph map (R02)',
         {rid: sorted(righe[rid].get('proposto_principi') or []) or ['nessuno'] for rid in mie}),
        ('L04', 'L04, one reading', 'DeepSeek, the passage, without the case dossier', una(L4)),
        ('L05', 'L05, one reading', 'DeepSeek, dossier and footnote rule, principle decided on the supported sentence', una(L5)),
        ('L05c', 'L05 with the paragraph map', 'composed as the platform shows it (R02)', composta(L5)),
        ('L06', 'L06, 2 of 4 readings', 'L05 instructions, principle decided on the whole passage (test)', due_su_quattro(L6)),
        ('opus', 'Claude Opus, blind', 'judged from the document alone, without proposals',
         {rid: sorted(set(g.get('principi') or []) - {'nessuno'}) or ['nessuno'] for rid, g in opus.items() if rid in mie}),
    ]
    prova = {
        'titolo': "Urgenda: the rows judged by Giuseppe Naglieri, again and blind",
        'descrizione': ('The rows of Urgenda that Giuseppe Naglieri judged in Uptakes, in a new order, without the machine\'s '
                        'proposals and without any earlier judgment. Your answers here do not change the rows. At the end you '
                        'see how L04, L05, L06, a blind reading by Claude Opus and his earlier judgment compare with yours.'),
        'caso': 'urgenda', 'righe': mie, 'per': [PI], 'domanda': 'principi', 'stato': 'aperta',
        'creata_il': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'creata_da': 'sabin-corpus/tools/crea_prova.py',
    }
    print(PROVA, len(mie), 'righe;', ', '.join(f'{c}: {len(v)}' for c, _, _, v in varianti))
    if not a.scrivi:
        return
    ref = db.collection('trace_prove').document(PROVA)
    ref.set(prova, merge=True)   # merge: non si perde `riservata`, scelta dal portale
    for i, (c, nome, nota, v) in enumerate(varianti):
        ref.collection('varianti').document(c).set({'nome': nome, 'nota': nota, 'ordine': i, 'principi': v})
    print('scritta')


if __name__ == '__main__':
    main()
