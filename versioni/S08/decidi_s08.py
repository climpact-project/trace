"""S08, LA DECISIONE SULLE COPPIE: una = unire, due = tenere, dubbio = al team (05/10/2026).

La regola del PI (04-05/10/2026): i riferimenti vicini allo stesso caso nello stesso atto sono coppie candidate; DeepSeek (L13,
cinque letture) e il reranker che ragiona (tre letture) leggono ciascuna coppia per intero e rispondono «una citazione o due?».
  una   i due lettori dicono UNA e nessun indizio forte dice DUE: si uniscono come C03 (resta una riga, l'altra le resta
        attaccata come appoggio: `unita_a`, `esclusa_regola` «S08»);
  due   i due lettori dicono DUE e nessun indizio forte dice UNA: contano due righe, non si scrive niente;
  team  tutti gli altri casi: disaccordo fra i due lettori, un lettore incerto o senza risposte valide (i freni di freni.py
        hanno scartato le sue letture), un indizio forte che contraddice i lettori. La coppia va in «To review».
S08 sostituisce la regola automatica di C03 per le righe NUOVE: la regola C03 (`unisci_c03.coppie`) resta solo come generatore
di candidate.

QUALE RIGA RESTA (quando e' «una»), in quest'ordine: la riga non scartata dal team; la confermata dal team; la riga nel testo
(non in nota, da `coppia_s08`: il testo dell'atto, non `proposto_posizione`, che e' sbagliata in molte righe); la principale
indicata dai lettori (maggioranza di A o B); la prima nell'atto. Per le TRADUZIONI (due atti in lingue diverse) S08 non decide:
restano a C03 con la lingua originale rivista a mano (la regola dell'intestazione sbagliava 46 volte su 105).

SENZA --scrivi NON SCRIVE NIENTE: stampa e salva le decisioni e le scritture PREPARATE, nello stesso formato di
tools/unisci_c03.py. Le righe NUOVE della scansione non hanno ancora un codice in banca: la coppia si decide ma la scrittura
aspetta che siano caricate (`scrittura: rinviata`).

    python tools/decidi_s08.py decidi  --banca F --richieste R.jsonl.gz --ds esiti_ds.json --rr esiti_rr.json --uscita cartella
    python tools/decidi_s08.py valuta  --banca F [--ds ... --rr ...]     # le coppie C03 riviste come verita': quante ne indovina
"""
import argparse
import collections
import csv
import datetime
import gzip
import json
import pathlib
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
import coppia_s08 as CS  # noqa: E402

MIN_DS = 3              # su cinque letture valide: almeno tre uguali (come L05)
MIN_RR = 2              # su tre letture valide: almeno due uguali
CODICE = 'S08'


class Lettore:
    """Il verdetto di un lettore su una coppia, dai voti di `leggi_coppia_l13.raccogli`."""

    def __init__(self, nome, minimo):
        self.nome, self.minimo = nome, minimo

    def verdetto(self, raccolta):
        """({'una'|'due'|'incerta'|None}, voti): None = nessuna lettura valida (freni) o nessuna lettura"""
        if not raccolta or not raccolta.get('valide'):
            return None, {}
        voti = raccolta['voti']
        esito, n = max(voti.items(), key=lambda kv: kv[1])
        if sum(1 for v in voti.values() if v == n) > 1 or n < self.minimo:
            return 'incerta', voti            # parita' o nessuna maggioranza
        return esito, voti

    @staticmethod
    def principale(raccolta):
        """la riga principale indicata dalla maggioranza delle letture valide «una» (A o B), o ''"""
        c = collections.Counter((x['json'].get('riga_principale') or '') for x in (raccolta or {}).get('letture', [])
                                if x['valida'] and x['json'].get('esito') == 'una')
        c.pop('', None)
        return c.most_common(1)[0][0] if c else ''


class Decisione:
    """L'esito di una coppia: `esito` una/due/team, il motivo, la riga che resta, i voti e gli indizi."""

    def __init__(self, id_coppia, esito, motivo, tenuta=None, esce=None, **extra):
        self.id, self.esito, self.motivo, self.tenuta, self.esce, self.extra = id_coppia, esito, motivo, tenuta, esce, extra

    def riga(self):
        return {'id': self.id, 'esito': self.esito, 'motivo': self.motivo,
                'tiene': (self.tenuta or {}).get('codice'), 'esce': (self.esce or {}).get('codice'), **self.extra}


class Decisore:
    """Mette insieme i due lettori e gli indizi. Con `solo_indizi=True` decide solo con gli indizi forti (nessun lettore: serve a
    provare l'impianto sulle coppie C03 riviste e a dire quante coppie gli indizi da soli lasciano al team)."""

    def __init__(self, solo_indizi=False):
        self.ds, self.rr = Lettore('DeepSeek L13', MIN_DS), Lettore('Qwen3.5-9B', MIN_RR)
        self.solo_indizi = solo_indizi

    @staticmethod
    def giudizio(r):
        return r.get('esito') or ''

    def riga_tenuta(self, c, principale=''):
        """(tenuta, esce) fra le due righe della coppia, con la regola dichiarata in testa al file"""
        a, b = c.a, c.b
        sc = (self.giudizio(a) == 'scartata', self.giudizio(b) == 'scartata')
        if sc[0] != sc[1]:
            return (b, a) if sc[0] else (a, b)
        cf = (self.giudizio(a) == 'confermata', self.giudizio(b) == 'confermata')
        if cf[0] != cf[1]:
            return (a, b) if cf[0] else (b, a)
        pa, pb = c._posizione(a), c._posizione(b)
        if pa != pb:
            return (a, b) if pa == 'testo' else (b, a)
        if principale in ('A', 'B'):
            return (a, b) if principale == 'A' else (b, a)
        return a, b

    def decidi(self, c, raccolta_ds=None, raccolta_rr=None):
        ind = c.indizi()
        i_esito, i_motivo, i_forte = CS.verdetto_indizi(ind)
        extra = {'indizio': i_esito or '', 'indizio_motivo': i_motivo, 'indizio_forte': int(i_forte),
                 'distanza': ind['distanza'], 'stessa_pagina': int(ind['stessa_pagina'])}
        if self.solo_indizi:
            if i_esito == 'una' and i_forte:
                t, e = self.riga_tenuta(c)
                return Decisione(c.id, 'una', 'solo indizi: ' + i_motivo, t, e, **extra)
            return Decisione(c.id, 'team', 'senza lettori nessun indizio forte', **extra)
        d, vd = self.ds.verdetto(raccolta_ds)
        r, vr = self.rr.verdetto(raccolta_rr)
        extra |= {'voti_ds': json.dumps(vd, ensure_ascii=False), 'voti_rr': json.dumps(vr, ensure_ascii=False),
                  'ds': d or '', 'rr': r or ''}
        if d is None or r is None:
            return Decisione(c.id, 'team', 'manca un lettore o tutte le sue letture sono state scartate dai freni', **extra)
        if d == 'incerta' or r == 'incerta':
            return Decisione(c.id, 'team', 'un lettore e\' incerto o senza maggioranza', **extra)
        if d != r:
            return Decisione(c.id, 'team', f'disaccordo: DeepSeek {d}, reranker {r}', **extra)
        if i_forte and i_esito != d:
            return Decisione(c.id, 'team', f'i lettori dicono {d} ma un indizio forte dice {i_esito} ({i_motivo})', **extra)
        if d == 'due':
            return Decisione(c.id, 'due', 'i due lettori dicono due citazioni', **extra)
        principale = self.ds.principale(raccolta_ds) or self.rr.principale(raccolta_rr)
        t, e = self.riga_tenuta(c, principale)
        return Decisione(c.id, 'una', 'i due lettori dicono una citazione', t, e, **extra)


class Scritture:
    """Le scritture PREPARATE (mai eseguite qui senza --scrivi), nello stesso formato di tools/unisci_c03.py: sulla riga che esce
    `proposto_rete` «esclusa», `esclusa_rete_prima`, `esclusa_regola` «S08», `unita_a`, `esclusa_motivo`, `esclusa_da`; sulla riga
    tenuta `proposto_nota_appoggio`, `proposto_paragrafi` uniti, `s08_da`. Una catena (A tiene B, B tiene C) si chiude sulla riga
    finale; una riga che esce in due coppie esce una volta; una riga senza codice (nuova) rinvia la scrittura."""

    def __init__(self, banca, da='S08'):
        self.banca, self.da = banca, da
        self.id_di = {r.get('codice'): i for i, r in banca.items() if r.get('codice')}

    def prepara(self, decisioni):
        import unisci_c03 as U
        tenuta_di = {d.esce['codice']: d.tenuta['codice'] for d in decisioni
                     if d.esito == 'una' and d.tenuta.get('codice') and d.esce.get('codice')}

        def finale(c, passi=0):
            return finale(tenuta_di[c], passi + 1) if c in tenuta_di and passi < 10 else c

        out, visti, saltate = {}, set(), collections.Counter()
        cod = {r.get('codice'): r for r in self.banca.values() if r.get('codice')}
        for d in decisioni:
            if d.esito != 'una':
                continue
            if not d.tenuta.get('codice') or not d.esce.get('codice'):
                saltate['scrittura rinviata: riga nuova senza codice in banca'] += 1
                continue
            t, n = cod.get(finale(d.tenuta['codice'])), cod.get(d.esce['codice'])
            if not t or not n or t is n:
                saltate['riga assente o catena chiusa su se stessa'] += 1
                continue
            if n['codice'] in visti:
                saltate['riga che esce gia\' in un\'altra coppia'] += 1
                continue
            if n.get('proposto_rete') not in U.ATTIVE or t.get('proposto_rete') not in U.ATTIVE or t.get('esito') == 'scartata':
                saltate['una riga non e\' piu\' viva o la tenuta e\' scartata'] += 1
                continue
            visti.add(n['codice'])
            ine, it = self.id_di[n['codice']], self.id_di[t['codice']]
            out[ine] = {'proposto_rete': 'esclusa', 'esclusa_rete_prima': n.get('proposto_rete'), 'esclusa_regola': CODICE,
                        'unita_a': t['codice'], 'esclusa_motivo': f'{CODICE} {d.motivo}', 'esclusa_da': self.da}
            ct = out.setdefault(it, {'s08_da': self.da})
            ct.setdefault('proposto_nota_appoggio', []).append(U.appoggio(t, n))
            ct['proposto_paragrafi'] = sorted(set(ct.get('proposto_paragrafi') or t.get('proposto_paragrafi') or [])
                                              | set(n.get('proposto_paragrafi') or []))
        return out, dict(saltate)


# ── valuta: le coppie C03 riviste come verita' ───────────────────────────────────────────────────────────────────

def valuta(banca, verita, raccolta_ds=None, raccolta_rr=None, solo_indizi=False):
    """Le 692 coppie C03 riviste a mano nello stesso atto (UNIRE = una, TENERE = due). Per ogni coppia la decisione di S08; poi i conti:
    giuste, sbagliate (una al posto di due o viceversa), al team; e per le UNIRE decise «una» quante volte S08 tiene la riga giusta."""
    import coppie_vicine as CV
    tara = CV.Taratura(banca, verita)
    righe = {r['id']: r for r in tara.righe}
    dec = Decisore(solo_indizi)
    conti, riga_giusta, rg_tot, esempi = collections.Counter(), 0, 0, collections.defaultdict(list)
    tutte = []
    for d, a, b, i in tara.coppie_stesso_atto():
        c = CS.Coppia(a, b, f"{a['codice']}__{b['codice']}")
        x = dec.decidi(c, (raccolta_ds or {}).get(c.id), (raccolta_rr or {}).get(c.id))
        attesa = 'una' if d == 'UNIRE' else 'due'
        conti[(attesa, x.esito)] += 1
        if x.esito == 'team':
            esempi[attesa].append(i)
        tutte.append((i, attesa, x))
        if d == 'UNIRE':       # quale riga resta, anche per le coppie che S08 manda al team (la regola sola)
            t, _ = dec.riga_tenuta(c)
            rg_tot += 1
            riga_giusta += int(t['codice'] == righe[i]['riga_da_tenere'])
    n = collections.Counter()
    for (att, esito), v in conti.items():
        n[att] += v
    ris = {'coppie': dict(n), 'matrice': {f'{k[0]}->{k[1]}': v for k, v in sorted(conti.items())},
           'decise_giuste': conti[('una', 'una')] + conti[('due', 'due')],
           'decise_sbagliate': conti[('una', 'due')] + conti[('due', 'una')],
           'al_team': conti[('una', 'team')] + conti[('due', 'team')],
           'riga_tenuta_giusta_sulle_unire': f'{riga_giusta}/{rg_tot}', 'modo': 'solo indizi' if solo_indizi else 'lettori + indizi'}
    d_tot = ris['decise_giuste'] + ris['decise_sbagliate']
    ris['precisione_sulle_decise'] = round(ris['decise_giuste'] / d_tot, 4) if d_tot else None
    ris['quota_decise'] = round(d_tot / sum(n.values()), 4)
    return ris, tutte


def carica(p):
    return json.load(gzip.open(p, 'rt', encoding='utf-8') if str(p).endswith('.gz') else open(p, encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='verbo', required=True)
    for nome in ('decidi', 'valuta'):
        p = sp.add_parser(nome)
        p.add_argument('--banca', required=True); p.add_argument('--ds', default=''); p.add_argument('--rr', default='')
        p.add_argument('--uscita', default=str(QUI / 'training' / 's08'))
        if nome == 'valuta':
            p.add_argument('--verita', default=str(QUI / 'training' / 'misure' / 'C03-REVISIONE-COPPIE-2026-10-04.tsv'))
        else:
            p.add_argument('--richieste', required=True)
            p.add_argument('--scrivi', action='store_true', help='NON ABILITATO in questa versione (vietato scrivere in banca dati)')
            p.add_argument('--da', default='')
    a = ap.parse_args()
    import coppie_vicine as CV
    banca = CV.carica_banca(a.banca)
    ds = carica(a.ds) if a.ds else None
    rr = carica(a.rr) if a.rr else None
    out = pathlib.Path(a.uscita); out.mkdir(parents=True, exist_ok=True)
    if a.verbo == 'valuta':
        ris, tutte = valuta(banca, a.verita, ds, rr, solo_indizi=not (ds and rr))
        json.dump(ris, open(out / 'valutazione_2026-10-05.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(json.dumps(ris, ensure_ascii=False, indent=1))
        return
    if a.scrivi:
        raise SystemExit('--scrivi non e\' abilitato: S08 si scrive in banca dati solo dopo la prova sulle coppie C03 e il si\' del PI')
    dec = Decisore()
    decisioni = []
    for r in carica(a.richieste) if str(a.richieste).endswith('.json') else [json.loads(l) for l in gzip.open(a.richieste, 'rt', encoding='utf-8')]:
        ca, cb = r['codici']
        ra = next((x for x in banca.values() if ca and x.get('codice') == ca), None)
        rb = next((x for x in banca.values() if cb and x.get('codice') == cb), None)
        if not ra or not rb:
            continue          # coppie con righe nuove: si decidono quando le righe sono in banca
        decisioni.append(dec.decidi(CS.Coppia(ra, rb, r['id']), (ds or {}).get(r['id']), (rr or {}).get(r['id'])))
    with open(out / 'decisioni_s08.tsv', 'w', newline='', encoding='utf-8') as h:
        w = csv.DictWriter(h, list(decisioni[0].riga().keys()), delimiter='\t', extrasaction='ignore')
        w.writeheader()
        w.writerows(d.riga() for d in decisioni)
    scr, saltate = Scritture(banca, a.da or 'S08').prepara(decisioni)
    json.dump({'data': datetime.date.today().isoformat(), 'scritture': scr, 'saltate': saltate}, open(out / 'scritture_s08_A_SECCO.json', 'w'), ensure_ascii=False)
    print(collections.Counter(d.esito for d in decisioni), 'scritture preparate:', len(scr), saltate, '(A SECCO: niente scritto)')


if __name__ == '__main__':
    main()
