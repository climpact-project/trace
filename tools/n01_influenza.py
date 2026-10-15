"""N01, l'influenza di una decisione e dei suoi principi (beta, 11/10/2026).

Metodo: pubblicazione/influenza/METODO-INFLUENZA-BOZZA.md. In breve:
  - l'unita' e' il CASO citante (la controversia); la riga e' la prova;
  - ogni coppia caso-decisione sta sul gradino piu' alto raggiunto da una sua riga:
      R1 menzione, R2 mobilitazione (parte/amicus/interveniente che argomenta),
      R3 attenzione giudiziale (la corte la nomina), R4 ricezione giudiziale (la corte la usa in motivazione);
  - tre misure separate: portata (>=R1), mobilitazione (>=R2), ricezione giudiziale (R4);
  - nessun peso fisso: i pesi esistono solo nella sensibilita', estratti a caso nel rispetto dell'ordine dei gradini;
  - l'errore di lettura della macchina entra nel conto (matrice di confusione dai validati, imputazione multipla).

Deterministico, nessun modello. SOLA LETTURA su corpus_rows. Scrive solo i propri file (e, con --scrivi,
le proprie schede in trace_versioni / trace_misure).

Uso:
  .venv/bin/python tools/n01_influenza.py --casi urgenda,neubauer [--da-file righe.json] [--scrivi]
"""
from __future__ import annotations

import argparse, collections, datetime as dt, hashlib, json, pathlib, random, statistics, sys

QUI = pathlib.Path(__file__).resolve().parent.parent
CARTELLA = QUI / 'pubblicazione' / 'influenza'
SOGLIE = CARTELLA / 'n01_soglie.json'
GIURISDIZIONI = CARTELLA / 'n01_giurisdizioni.json'
DATE_DOC = QUI / 'pubblicazione' / 'mappa' / 'date_documenti.json'
CONTROVERSIE = CARTELLA / 'n01_controversie.json'
PREFISSI = {'urgenda': 'URG', 'neubauer': 'NEU', 'future-generations': 'FGC', 'klimaseniorinnen': 'KLS',
            'cig-parere-clima': 'ICJ', 'idh-oc-32-25': 'IAC'}
GRADINI = (1, 2, 3, 4)
PESI_ATTESI = {1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}


def _codici_pubblici():
    """I codici delle citazioni che il database pubblico di TRACE 0.1 mostra (il file del rilascio)."""
    import csv
    f = QUI / 'pubblicazione' / 'trace-0.1' / 'zenodo-dati' / 'trace-0.1-citations.csv'
    if not f.exists():
        return set()
    with f.open(encoding='utf-8') as h:
        return {r['citation_code'] for r in csv.DictReader(h)}


CODICI_PUBBLICI = _codici_pubblici()
PAESI_TAB = json.loads((pathlib.Path(__file__).resolve().parent.parent / 'pubblicazione' / 'influenza' / 'n01_paesi.json').read_text())


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ── lettura ──────────────────────────────────────────────────────────────────────────────────────────────────

def leggi_firestore(casi):
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    c = firestore.Client(project='climpact-drp')
    out = {}
    for caso in casi:
        pre = PREFISSI[caso]
        q = (c.collection('corpus_rows').where(filter=FieldFilter('codice', '>=', pre + '-'))
             .where(filter=FieldFilter('codice', '<', pre + '.')).order_by('codice'))
        out[caso] = [dict(d.to_dict(), _id=d.id) for d in q.stream()]
    return out


def leggi_file(percorso, casi):
    d = json.loads(pathlib.Path(percorso).read_text())
    return {caso: d.get(PREFISSI[caso], d.get(caso, [])) for caso in casi}


def unisci_controversie(dati, tabella):
    """I casi di una stessa raccolta (bundle) del database diventano un caso solo (regola del PI, 15/10/2026).

    Il caso che resta e' quello della raccolta con piu' righe (a parita', il primo in ordine): cosi' id e nome restano
    quelli di una scheda vera del database. L'id originale resta in 'case_id_originale'."""
    mappa = tabella.get('caso_controversia', {})
    righe_per = collections.Counter(r.get('case_id') for rs in dati.values() for r in rs)
    rappr = {}
    for cid, n in sorted(righe_per.items(), key=lambda kv: (-kv[1], kv[0])):
        b = mappa.get(cid)
        if b and b not in rappr:
            rappr[b] = cid
    nomi = {}
    for rs in dati.values():
        for r in rs:
            nomi.setdefault(r.get('case_id'), r.get('case_name'))
    unite = collections.defaultdict(set)
    for rs in dati.values():
        for r in rs:
            b = mappa.get(r.get('case_id'))
            if b and rappr[b] != r.get('case_id'):
                unite[rappr[b]].add(r['case_id'])
                r['case_id_originale'] = r['case_id']
                r['case_id'] = rappr[b]
                r['case_name'] = nomi[rappr[b]]
    return {k: sorted(v) for k, v in unite.items()}


# ── campi ────────────────────────────────────────────────────────────────────────────────────────────────────

def campo(r, nome, solo_proposto=False):
    if not solo_proposto:
        v = r.get('validato_' + nome)
        if v not in (None, '', []):
            return v
    return r.get('proposto_' + nome)


def validata(r):
    return r.get('esito') == 'confermata' or bool(r.get('validato_tipo_citazione') or r.get('validato_chi_parla'))


def motivo_esclusione(r, S):
    rete = r.get('proposto_rete')
    if rete == 'fusa':
        return 'fusa'
    if rete == 'esclusa':
        return 'esclusa'
    if r.get('scartato') is True:
        return 'scartato'
    if r.get('esito') == 'scartata':
        return 'esito_scartata'
    if rete not in S['reti_vive']:
        return 'rete_non_viva'
    return None


def luogo(r, solo_proposto=False):
    """(opinione, parte, voce) della citazione nell'atto (L16 fase B, L17 fase C; §29.2 punto 3): la decisione nel
    portale, poi la proposta. None dove la fase non c'e' ancora."""
    sz, vc = r.get('proposto_sezione') or {}, r.get('proposto_voce') or {}
    man = (lambda k: None) if solo_proposto else (lambda k: r.get(k) or None)
    return (man('validato_opinione') or sz.get('opinione') or None,
            man('validato_parte_atto') or sz.get('parte') or None,
            man('validato_voce') or vc.get('voce') or None)


def in_motivazione(r, S, solo_proposto=False):
    """PROPOSTA A, scelta dal PI il 15/10/2026: dove la mappa dell'atto c'e', decide lei. In R4 solo la motivazione
    della maggioranza, con la corte che parla con parole sue o riassume; fatti, difese riportate, dispositivo, opinioni
    separate e testo altrui copiato restano R3. Una voce non ancora letta (fase C) non toglie niente. Dove la mappa non
    c'e' (atti non letti dalla fase B) resta la `sede` di prima."""
    opinione, parte, voce = luogo(r, solo_proposto)
    A = S.get('sezione_R4')
    if A and (opinione or parte):
        return (opinione in A['opinione'] and parte in A['parte'] and (voce is None or voce in A['voce']))
    return (campo(r, 'sede', solo_proposto) or '') in S['sede_motivazione']


def gradino(r, S, solo_proposto=False, variante='base'):
    tipo = campo(r, 'tipo_citazione', solo_proposto) or ''
    voce = campo(r, 'chi_parla', solo_proposto) or ''
    argomentativo = tipo in S['tipi_argomentativi'] or (variante == 'descrittiva_argomenta' and tipo == 'descrittiva')
    if voce in S['voce_corte']:
        if variante == 'corte_ovunque_R4':
            return 4
        return 4 if (in_motivazione(r, S, solo_proposto) and argomentativo) else 3
    return 2 if argomentativo else 1


def principi(r, S, con_senza_prova=False):
    ps = [p for p in (campo(r, 'principi') or []) if p]
    if not con_senza_prova:
        senza = set(r.get('proposto_principi_senza_prova') or [])
        if not r.get('validato_principi'):
            ps = [p for p in ps if p not in senza]
    return ps


class Giur:
    def __init__(self, tabella):
        self.paesi = set(tabella['paesi'])
        self.fori = tabella['fori']

    def __call__(self, s):
        parti = [p.strip() for p in str(s or '').split(';') if p.strip()]
        for p in parti:
            if p in self.paesi:
                return p
        for p in parti:
            if p in self.fori:
                return self.fori[p]
        return 'non determinata'


# ── misure ───────────────────────────────────────────────────────────────────────────────────────────────────

def coppie(righe, S, giur, date_doc, variante='base', gradini_righe=None):
    """Un dizionario caso -> {gradino, documenti, giurisdizione, anno, righe} per una decisione."""
    casi = {}
    for i, r in enumerate(righe):
        g = gradini_righe[i] if gradini_righe is not None else gradino(r, S, variante=variante)
        c = casi.setdefault(r.get('case_id'), {'gradino': 0, 'documenti': set(), 'giur': giur(r.get('giurisdizioni')),
                                               'date': [], 'righe': 0, 'tipi_R4': collections.Counter(),
                                               'nome': r.get('case_name') or '', 'codice': '', 'chiave_codice': (-1, 0, 0)})
        # la citazione che da' al caso il suo gradino: la piu' alta, poi una che il database pubblico mostra, poi una
        # controllata dal team (il link «Open the citation» della pagina deve aprire qualcosa)
        k = (g, 1 if r.get('codice') in CODICI_PUBBLICI else 0, 1 if validata(r) else 0)
        if k > c['chiave_codice']:
            c['chiave_codice'] = k
            c['codice'] = r.get('codice') or ''
        c['gradino'] = max(c['gradino'], g)
        c['documenti'].add(r.get('document_id'))
        c['righe'] += 1
        if g == 4:
            c['tipi_R4'][campo(r, 'tipo_citazione')] += 1
        d = (date_doc.get(r.get('document_id')) or {}).get('data_documento') or str(r.get('data') or '')[:10]
        if len(d) == 4 and d.isdigit():
            d += '-07-01'  # solo l'anno: meta' anno, dichiarato nel metodo
        if len(d) == 10:
            c['date'].append(d)
    return casi


def riassunto(casi, data_decisione):
    per = collections.Counter(c['gradino'] for c in casi.values())
    giur = lambda soglia: sorted({c['giur'] for c in casi.values() if c['gradino'] >= soglia})
    curva = collections.Counter()
    for c in casi.values():
        if c['date']:
            anni = (dt.date.fromisoformat(min(c['date'])[:10]) - dt.date.fromisoformat(data_decisione)).days / 365.25
            curva[max(0, int(anni))] += 1
    prof = collections.Counter()
    for c in casi.values():
        for t in c['tipi_R4']:
            prof[t] += 1
    return {
        'casi_per_gradino': {f'R{g}': per.get(g, 0) for g in GRADINI},
        'portata_casi': sum(per.values()),
        'mobilitazione_casi': sum(per.get(g, 0) for g in (2, 3, 4)),
        'ricezione_giudiziale_casi': per.get(4, 0),
        'attenzione_giudiziale_casi': per.get(3, 0) + per.get(4, 0),
        'giurisdizioni_portata': len(giur(1)),
        'giurisdizioni_ricezione': len(giur(4)),
        'elenco_giurisdizioni_ricezione': giur(4),
        'documenti': len({d for c in casi.values() for d in c['documenti']}),
        'curva_casi_per_anni_dalla_decisione': dict(sorted(curva.items())),
        'profilo_R4_casi_per_tipo': dict(prof),
    }


def pagine_che_proseguono(r):
    """Le pagine attorno su cui la macchina (o la persona) dice che il ragionamento prosegue."""
    est = r.get('validato_estensione') or r.get('proposto_estensione') or []
    if isinstance(est, str):
        return 0
    return sum(1 for e in est if isinstance(e, dict) and e.get('prosegue') is True)


def paragrafi(r):
    ps = r.get('validato_paragrafi') or r.get('proposto_paragrafi') or []
    return [p for p in ps if isinstance(p, str) and p]


def misure_fini(righe, gradini_righe, esiti, giur=None, date_doc=None, data_decisione=None):
    """Le misure piu' fini (11/10/2026, il PI): i passaggi usati, la profondita' della ricezione giudiziale, l'esito.

    - passaggi: per paragrafo della sentenza, i casi che lo usano in R4 e quelli in R2 o piu';
    - profondita': per ogni caso in R4, quante pagine attorno proseguono il ragionamento (il massimo fra le sue righe R4);
    - esito: casi per gradino e per esito del caso citante per chi l'ha portato (letto in automatico, non verificato).
    """
    pas = collections.defaultdict(lambda: {'R4': set(), 'R2+': set()})
    tipi_R4 = collections.defaultdict(set)   # tipo di citazione -> casi in R4 che lo usano (seguire, distinguere, criticare)
    giur_R4 = collections.defaultdict(set)   # giurisdizione -> casi in R4
    prima = {}                               # (caso, gradino) -> data del primo documento a quel gradino
    date_doc = date_doc or {}
    prof = {}
    gcaso = {}
    for r, g in zip(righe, gradini_righe):
        cid = r.get('case_id')
        gcaso[cid] = max(gcaso.get(cid, 0), g)
        for p in paragrafi(r):
            if g >= 2:
                pas[p]['R2+'].add(cid)
            if g == 4:
                pas[p]['R4'].add(cid)
        if g == 4:
            prof[cid] = max(prof.get(cid, 0), pagine_che_proseguono(r))
            tipi_R4[campo(r, 'tipo_citazione') or ''].add(cid)
            if giur:
                giur_R4[giur(r.get('giurisdizioni'))].add(cid)
        dd = (date_doc.get(r.get('document_id')) or {}).get('data_documento') or str(r.get('data') or '')[:10]
        if len(dd) == 4 and dd.isdigit():
            dd += '-07-01'
        if len(dd) == 10:
            k = (cid, g)
            prima[k] = min(prima.get(k, dd), dd)
    passaggi = sorted(({'paragrafo': p, 'casi_R4': len(v['R4']), 'casi_R2_piu': len(v['R2+'])} for p, v in pas.items()),
                      key=lambda x: (-x['casi_R4'], -x['casi_R2_piu'], x['paragrafo']))
    fasce = collections.Counter('0' if n == 0 else '1-2' if n <= 2 else '3+' for n in prof.values())
    con_paragrafi = len({r.get('case_id') for r, g in zip(righe, gradini_righe) if g == 4 and paragrafi(r)})
    esito = collections.defaultdict(collections.Counter)
    for cid, g in gcaso.items():
        e = ((esiti.get(cid) or {}).get('esito') or {})
        esito[f'R{g}'][(e.get('esito') if isinstance(e, dict) else None) or 'non_letto'] += 1
    curva = collections.defaultdict(collections.Counter)  # gradino -> anni dalla decisione -> casi che lo raggiungono la prima volta
    if data_decisione:
        d0 = dt.date.fromisoformat(data_decisione)
        primo_caso = {}
        for (cid, g), dd in prima.items():
            for h in range(1, g + 1):  # chi arriva a R4 e' anche a R1+
                primo_caso[(cid, h)] = min(primo_caso.get((cid, h), dd), dd)
        for (cid, h), dd in primo_caso.items():
            anni = max(0, int((dt.date.fromisoformat(dd) - d0).days / 365.25))
            curva[f'R{h}'][anni] += 1
    return {
        'uso_R4': {k: len(v) for k, v in tipi_R4.items()},
        'giurisdizioni_R4': dict(sorted(((k, len(v)) for k, v in giur_R4.items()), key=lambda kv: -kv[1])),
        'curva_per_gradino': {k: dict(sorted(v.items())) for k, v in sorted(curva.items())},
        'passaggi_R4': passaggi[:15], 'casi_R4_con_paragrafi': con_paragrafi,
        'profondita_R4': {'casi': len(prof), 'pagine_che_proseguono': dict(fasce),
                          'mediana': statistics.median(prof.values()) if prof else None},
        'esito_per_gradino': {k: dict(v) for k, v in sorted(esito.items())},
    }


PAESI = CARTELLA / 'n01_paesi.json'


def misure_nuove(caso, righe, gradini_righe, S, giur, date_doc, data_decisione, paesi, base, pc):
    """Le misure aggiunte l'11/10/2026 (il PI: «devi fare tutto»; revisione critica del metodo). Ognuna a se', dichiarata.

    - decomposizione: l'indice diviso fra cio' che portano le parti (R1, R2) e cio' che portano le corti (R3, R4);
    - conversione: fra i casi in cui una parte argomenta con la sentenza e una corte ha scritto un atto nel corpus, la
      quota in cui la corte la usa in motivazione (Hansford e Spriggs, la sopravvivenza di un precedente);
    - transnazionale: casi in R4 fuori dalla giurisdizione della sentenza, e la loro quota dell'indice;
    - velocita': anni dalla sentenza al primo caso in R4, e al primo caso in R4 di un'altra giurisdizione;
    - contestazione: fra i casi in R4, quelli dove la corte se ne distingue o la critica;
    - diffusione: famiglie giuridiche e continenti raggiunti (tabella dichiarata n01_paesi.json);
    - principi che viaggiano: principio per giurisdizione sui casi da R2 in su, con la quota transnazionale;
    - emivita: eta' mediana dei casi citanti (anni dalla sentenza al primo atto), solo dove la sentenza ha almeno otto anni.
    """
    home = set(paesi['home'].get(caso, []))
    tab = paesi['giurisdizioni']
    passi = collections.defaultdict(set)
    corte_nel_corpus = set()
    uso_R4 = collections.defaultdict(set)
    prima_R4 = {}
    prima = {}
    for r, g in zip(righe, gradini_righe):
        cid = r.get('case_id')
        passi[cid].add(g)
        if r.get('tipo_atto') == 'decisione':
            corte_nel_corpus.add(cid)
        dd = (date_doc.get(r.get('document_id')) or {}).get('data_documento') or str(r.get('data') or '')[:10]
        if len(dd) == 4 and dd.isdigit():
            dd += '-07-01'
        if len(dd) == 10:
            prima[cid] = min(prima.get(cid, dd), dd)
            # per la velocita' contano solo date DOPO la sentenza: una data anteriore e' quasi sempre l'anno del caso,
            # non la data dell'atto (il campo «data» di corpus_rows), e direbbe «zero anni» per errore
            if g == 4 and dd >= data_decisione:
                prima_R4[cid] = min(prima_R4.get(cid, dd), dd)
        if g == 4:
            uso_R4[campo(r, 'tipo_citazione') or ''].add(cid)
    d0 = dt.date.fromisoformat(data_decisione)
    anni = lambda d: round(max(0.0, (dt.date.fromisoformat(d) - d0).days / 365.25), 1)
    parti = sum(PESI_ATTESI[c['gradino']] for c in base.values() if c['gradino'] <= 2)
    corti = sum(PESI_ATTESI[c['gradino']] for c in base.values() if c['gradino'] >= 3)
    con_r2 = [cid for cid in corte_nel_corpus if 2 in passi[cid]]
    convertiti = [cid for cid in con_r2 if 4 in passi[cid]]
    r4 = [cid for cid, c in base.items() if c['gradino'] == 4]
    estero = [cid for cid in r4 if base[cid]['giur'] not in home]
    indice_estero = sum(PESI_ATTESI[c['gradino']] for c in base.values() if c['giur'] not in home)
    totale = parti + corti
    contestati = uso_R4.get('distinguente', set()) | uso_R4.get('critica', set())
    fam = collections.Counter(tab.get(c['giur'], ['non classificata', ''])[0] for c in base.values())
    cont_home = {tab.get(h, ['', ''])[1] for h in home}
    cont = collections.Counter(tab.get(c['giur'], ['', 'non classificato'])[1] for c in base.values())
    fuori_continente = sum(n for k, n in cont.items() if k not in cont_home)
    eta = sorted(anni(prima[cid]) for cid in base if cid in prima)
    eta_sentenza = (dt.date.today() - d0).days / 365.25
    # principi che viaggiano: principio -> giurisdizione -> casi (da R2 in su)
    viaggio = {}
    for p, casi in pc.items():
        if p in S['principi_neutri']:
            continue
        per_g = collections.Counter(base[cid]['giur'] for cid, (g, _) in casi.items() if g >= 2 and cid in base)
        if per_g:
            tot_p = sum(per_g.values())
            viaggio[p] = {'giurisdizioni': dict(per_g.most_common()), 'casi': tot_p,
                          'quota_transnazionale': round(sum(n for k, n in per_g.items() if k not in home) / tot_p, 3)}
    return {
        'decomposizione': {'parti': round(parti, 2), 'corti': round(corti, 2), 'quota_corti': round(corti / totale, 3) if totale else None},
        'conversione': {'casi_con_parte_e_corte': len(con_r2), 'convertiti': len(convertiti),
                        'tasso': round(len(convertiti) / len(con_r2), 3) if con_r2 else None},
        'transnazionale': {'casi_R4': len(r4), 'casi_R4_estero': len(estero), 'quota_R4': round(len(estero) / len(r4), 3) if r4 else None,
                           'quota_indice': round(indice_estero / totale, 3) if totale else None},
        'velocita': {'anni_primo_R4': min((anni(prima_R4[c]) for c in r4 if c in prima_R4), default=None),
                     'anni_primo_R4_estero': min((anni(prima_R4[c]) for c in estero if c in prima_R4), default=None)},
        'contestazione': {'casi_R4': len(r4), 'contestati': len(contestati & set(r4)),
                          'quota': round(len(contestati & set(r4)) / len(r4), 3) if r4 else None},
        'diffusione': {'famiglie': dict(fam), 'n_famiglie': len([k for k in fam if k != 'non classificata']),
                       'continenti': dict(cont), 'quota_fuori_continente': round(fuori_continente / len(base), 3) if base else None},
        'emivita': {'eta_mediana_anni': statistics.median(eta) if eta and eta_sentenza >= 8 else None,
                    'anni_dalla_sentenza': round(eta_sentenza, 1), 'casi_datati': len(eta),
                    'nota': None if eta_sentenza >= 8 else 'too recent to estimate'},
        'principi_viaggio': dict(sorted(viaggio.items(), key=lambda kv: -kv[1]['casi'])),
    }


def principi_per_caso(righe, S, gradini_righe, modo='intero'):
    """principio -> caso -> (gradino massimo, quota). modo: intero | diviso | punteggio."""
    out = collections.defaultdict(dict)
    for r, g in zip(righe, gradini_righe):
        ps = principi(r, S)
        if not ps:
            continue
        punteggi = r.get('proposto_punteggi_principi') or {}
        for p in ps:
            if modo == 'diviso':
                q = 1 / len(ps)
            elif modo == 'punteggio':
                q = float(punteggi.get(p, 0) or 0) if isinstance(punteggi, dict) else 0.0
            else:
                q = 1.0
            vecchio = out[p].get(r.get('case_id'), (0, 0.0))
            out[p][r.get('case_id')] = (max(vecchio[0], g), max(vecchio[1], q))
    return out


def tabella_principi(pc, S):
    t = {}
    for p, casi in pc.items():
        per = collections.Counter(g for g, _ in casi.values())
        t[p] = {'casi': len(casi), 'casi_R2_piu': sum(per.get(g, 0) for g in (2, 3, 4)),
                'casi_R4': per.get(4, 0), 'neutro': p in S['principi_neutri'],
                'casi_per_gradino': {f'R{g}': per.get(g, 0) for g in GRADINI}}
    return dict(sorted(t.items(), key=lambda kv: (-kv[1]['casi_R4'], -kv[1]['casi'])))


# ── errore di lettura ────────────────────────────────────────────────────────────────────────────────────────

def matrice_confusione(tutte_righe, S):
    """P(gradino vero | gradino proposto) dalle righe dove una persona ha fissato chi parla E tipo (lisciata +1)."""
    m = {g: collections.Counter({h: 1 for h in GRADINI}) for g in GRADINI}
    n = 0
    for r in tutte_righe:
        if r.get('validato_chi_parla') and r.get('validato_tipo_citazione'):
            m[gradino(r, S, solo_proposto=True)][gradino(r, S)] += 1
            n += 1
    prob = {g: {h: m[g][h] / sum(m[g].values()) for h in GRADINI} for g in GRADINI}
    grezza = {f'R{g}': {f'R{h}': m[g][h] - 1 for h in GRADINI} for g in GRADINI}
    return prob, grezza, n


def imputa(righe, S, prob, rng):
    """Un gradino «vero» per ogni riga non controllata, estratto dalla matrice d'errore.

    L'ERRORE SI ESTRAE PER DOCUMENTO, NON PER RIGA (11/10/2026, revisione critica del metodo, punto 1). Le letture di uno
    stesso atto non sbagliano ognuna per conto suo: chi parla e la sede sono le stesse in tutto l'atto. Estrarre l'errore
    riga per riga e poi prendere il gradino massimo del caso faceva salire i casi in R4 solo perche' un caso ha molte righe
    (Neubauer da 26 a 49). Ora: una estrazione per (documento, gradino proposto), condivisa da tutte le righe di quel
    documento con quel gradino; le righe controllate dal team tengono il loro gradino.
    """
    scelte = {}
    out = []
    for r in righe:
        if r.get('validato_chi_parla') and r.get('validato_tipo_citazione'):
            out.append(gradino(r, S))
            continue
        g0 = gradino(r, S, solo_proposto=True)
        k = (r.get('document_id'), g0)
        if k not in scelte:
            p = prob[g0]
            x, acc, h_scelto = rng.random(), 0.0, 4
            for h in GRADINI:
                acc += p[h]
                if x <= acc:
                    h_scelto = h
                    break
            scelte[k] = h_scelto
        out.append(scelte[k])
    return out


def quantili(v):
    v = sorted(v)
    q = lambda f: v[min(len(v) - 1, int(f * (len(v) - 1) + 0.5))]
    return {'mediana': q(0.5), 'p05': q(0.05), 'p95': q(0.95)}


# ── sensibilita' ─────────────────────────────────────────────────────────────────────────────────────────────

def pesi_ordinati(rng):
    """Pesi uniformi sull'insieme {0 <= w1 <= w2 <= w3 <= w4 = 1}: tre uniformi ordinate."""
    a = sorted(rng.random() for _ in range(3))
    return {1: a[0], 2: a[1], 3: a[2], 4: 1.0}


def ranghi(punteggi):
    ordine = sorted(punteggi, key=lambda k: -punteggi[k])
    return {k: i + 1 for i, k in enumerate(ordine)}


def stabilita(oggetti_gradini, n, rng):
    """oggetti_gradini: nome -> lista di gradini (uno per caso). Rango con pesi ordinati estratti a caso."""
    conta = {k: collections.Counter() for k in oggetti_gradini}
    valori = {k: [] for k in oggetti_gradini}
    for _ in range(n):
        w = pesi_ordinati(rng)
        s = {k: sum(w[g] for g in gs) for k, gs in oggetti_gradini.items()}
        for k, rk in ranghi(s).items():
            conta[k][rk] += 1
            valori[k].append(s[k])
    out = {}
    for k in oggetti_gradini:
        modale, volte = conta[k].most_common(1)[0]
        out[k] = {'rango_modale': modale, 'probabilita_rango_modale': round(volte / n, 3),
                  'probabilita_primo': round(conta[k].get(1, 0) / n, 3),
                  'indice': {a: round(b, 2) for a, b in quantili(valori[k]).items()}}
    return dict(sorted(out.items(), key=lambda kv: kv[1]['rango_modale']))


# ── giro ─────────────────────────────────────────────────────────────────────────────────────────────────────

def calcola(dati, S, giur, date_doc, esiti=None):
    esiti = esiti or {}
    seme = S['sensibilita']['seme']
    tutte = [r for righe in dati.values() for r in righe]
    vive_tutte = [r for r in tutte if motivo_esclusione(r, S) is None]
    prob, grezza, n_conf = matrice_confusione(vive_tutte, S)
    risultato = {'matrice_confusione': {'righe': n_conf, 'proposto_vs_validato': grezza}, 'decisioni': {}}

    for caso, righe in dati.items():
        rng = random.Random(f'{seme}-{caso}')
        esclusi = collections.Counter(motivo_esclusione(r, S) or 'tenuta' for r in righe)
        vive = [r for r in righe if motivo_esclusione(r, S) is None]
        data_dec = S['date_decisioni'][caso]
        g_base = [gradino(r, S) for r in vive]
        base = coppie(vive, S, giur, date_doc, gradini_righe=g_base)
        val = [r for r in vive if validata(r)]

        # varianti delle soglie e della lettura
        varianti = {}
        for nome in ('corte_ovunque_R4', 'descrittiva_argomenta'):
            varianti[nome] = riassunto(coppie(vive, S, giur, date_doc, variante=nome), data_dec)['casi_per_gradino']
        sicure = [r for r in vive if r.get('proposto_confidenza') != 'bassa' and r.get('proposto_tipo_incerto') is not True]
        varianti['senza_bassa_confidenza_o_tipo_incerto'] = riassunto(coppie(sicure, S, giur, date_doc), data_dec)['casi_per_gradino']
        varianti['solo_validate'] = riassunto(coppie(val, S, giur, date_doc), data_dec)['casi_per_gradino']

        # errore di lettura: imputazione multipla + bootstrap sui casi
        imp = collections.defaultdict(list)
        indici = []
        ids = list(base)
        for _ in range(S['sensibilita']['imputazioni']):
            gi = imputa(vive, S, prob, rng)
            c = coppie(vive, S, giur, date_doc, gradini_righe=gi)
            campione = [c[rng.choice(ids)]['gradino'] for _ in ids]
            per = collections.Counter(campione)
            for g in GRADINI:
                imp[f'R{g}'].append(per.get(g, 0))
            w = pesi_ordinati(rng)  # l'indice con le tre incertezze insieme: lettura, casi, pesi
            indici.append(sum(w[g] for g in campione))
        varianti['corretta_per_errore_di_lettura'] = {k: quantili(v) for k, v in imp.items()}

        # IL TRACE JUDICIAL IMPACT INDEX (11/10/2026, il PI: «il numero finale»). Il peso di un gradino e' il suo valore
        # ATTESO sui pesi ammissibili (uniformi su 0 <= w1 <= w2 <= w3 <= w4 = 1): le statistiche d'ordine di tre uniformi
        # danno 1/4, 2/4, 3/4, quindi R1 0.25, R2 0.5, R3 0.75, R4 1. Non e' una scelta: e' la media di tutte le scelte
        # che rispettano l'ordine. Indice = somma sui casi citanti; intervallo = lettura + casi + pesi insieme.
        anni_trascorsi = max(0.5, (dt.date.today() - dt.date.fromisoformat(data_dec)).days / 365.25)
        valore = sum(PESI_ATTESI[c['gradino']] for c in base.values())
        q = quantili(indici)
        indice = {'valore': round(valore, 1), 'mediana': round(q['mediana'], 1), 'p05': round(q['p05'], 1), 'p95': round(q['p95'], 1),
                  'anni_dalla_decisione': round(anni_trascorsi, 1), 'per_anno': round(valore / anni_trascorsi, 1),
                  'per_anno_p05': round(q['p05'] / anni_trascorsi, 1), 'per_anno_p95': round(q['p95'] / anni_trascorsi, 1),
                  'tasso_ricezione_giudiziale': round(per_r4 / max(1, len(base)), 3) if (per_r4 := sum(1 for c in base.values() if c['gradino'] == 4)) is not None else None}

        # principi
        pc = principi_per_caso(vive, S, g_base)
        tab = tabella_principi(pc, S)
        for modo in ('diviso', 'punteggio'):
            alt = principi_per_caso(vive, S, g_base, modo)
            for p, casi in alt.items():
                tab.setdefault(p, {})[f'quota_{modo}'] = round(sum(q for _, q in casi.values()), 2)
        stab = stabilita({p: [g for g, _ in casi.values()] for p, casi in pc.items()
                          if p not in S['principi_neutri']}, S['sensibilita']['estrazioni_pesi'], rng)

        risultato['decisioni'][caso] = {
            'copertura': S['copertura'][caso], 'data_decisione': data_dec,
            'righe_lette': len(righe), 'righe_per_esito': dict(esclusi),
            'righe_vive': len(vive), 'righe_validate': len(val),
            'quota_validata': round(len(val) / max(1, len(vive)), 3),
            'indice': indice,
            'tutte': riassunto(base, data_dec),
            'solo_validate': riassunto(coppie(val, S, giur, date_doc), data_dec),
            'varianti': varianti,
            'principi': tab,
            'fini': misure_fini(vive, g_base, esiti, giur, date_doc, data_dec),
            'nuove': misure_nuove(caso, vive, g_base, S, giur, date_doc, data_dec, PAESI_TAB, base, pc),
            'stabilita_principi_pesi_ordinati': stab,
            'casi': {cid: {'gradino': f"R{c['gradino']}", 'giurisdizione': c['giur'], 'documenti': len(c['documenti']),
                           'righe': c['righe'], 'nome': c['nome'], 'codice': c['codice']} for cid, c in base.items()},
        }

    # fra decisioni: solo a parita' di anni dalla decisione, e con la copertura accanto
    rng = random.Random(f'{seme}-decisioni')
    risultato['stabilita_decisioni_pesi_ordinati'] = stabilita(
        {k: [int(c['gradino'][1]) for c in v['casi'].values()] for k, v in risultato['decisioni'].items()},
        S['sensibilita']['estrazioni_pesi'], rng)
    risultato['co_ricezione'] = co_ricezione(risultato['decisioni'])
    mappa = S.get('casi_delle_decisioni', {})
    risultato['tra_decisioni'] = [{'da': mappa[cid], 'a': k, 'gradino': c['gradino'], 'righe': c['righe']}
                                  for k, v in risultato['decisioni'].items() for cid, c in v['casi'].items()
                                  if cid in mappa and mappa[cid] != k]
    return risultato


def co_ricezione(decisioni):
    nomi = list(decisioni)
    out = {}
    for soglia in (1, 4):
        insiemi = {k: {c for c, v in decisioni[k]['casi'].items() if int(v['gradino'][1]) >= soglia} for k in nomi}
        tutti = set().union(*insiemi.values()) if insiemi else set()
        N = max(1, len(tutti))
        out[f'R{soglia}_o_piu'] = {a: {b: {'casi': len(insiemi[a] & insiemi[b]),
                                           'jaccard': round(len(insiemi[a] & insiemi[b]) / max(1, len(insiemi[a] | insiemi[b])), 3),
                                           # il coseno di Salton e l'atteso se le due ricezioni fossero indipendenti (Small 1973)
                                           'coseno': round(len(insiemi[a] & insiemi[b]) / max(1e-9, (len(insiemi[a]) * len(insiemi[b])) ** 0.5), 3) if insiemi[a] and insiemi[b] else 0,
                                           'atteso': round(len(insiemi[a]) * len(insiemi[b]) / N, 1)}
                                       for b in nomi if b != a} for a in nomi}
    return out


def leggi_esiti(fonte):
    """caso -> voce del file dei casi della mappa (con 'esito'). Vuoto se non si legge: la misura lo dice."""
    import gzip, subprocess
    try:
        if fonte.startswith('gs://'):
            grezzo = subprocess.run(['gsutil', '-q', 'cat', fonte], check=True, capture_output=True).stdout
        else:
            grezzo = pathlib.Path(fonte).read_bytes()
        if grezzo[:2] == b'\x1f\x8b':
            grezzo = gzip.decompress(grezzo)
        return json.loads(grezzo).get('casi', {})
    except Exception as e:  # noqa: BLE001
        print('esiti non letti:', e)
        return {}


def per_il_sito(r):
    """Solo cio' che il pannello Numbers mostra: niente id dei casi, niente elenchi lunghi."""
    out = {'versione': r['versione'], 'righe_matrice_confusione': r['matrice_confusione']['righe'],
           'co_ricezione': r['co_ricezione'],
           'tra_decisioni': r['tra_decisioni'],
           'decisioni': {}}
    for k, d in r['decisioni'].items():
        stab = d['stabilita_principi_pesi_ordinati']
        principi = []
        for p, v in d['principi'].items():
            s = stab.get(p, {})
            principi.append({'id': p, **{x: v.get(x) for x in ('casi', 'casi_R2_piu', 'casi_R4', 'casi_per_gradino', 'neutro',
                                                             'quota_diviso', 'quota_punteggio')},
                             'rango': s.get('rango_modale'), 'stabile': s.get('probabilita_rango_modale'),
                             'primo': s.get('probabilita_primo')})
        t = dict(d['tutte'])
        out['decisioni'][k] = {
            'copertura': d['copertura'], 'data': d['data_decisione'], 'righe': d['righe_vive'],
            'righe_validate': d['righe_validate'], 'quota_validata': d['quota_validata'],
            'righe_per_esito': d['righe_per_esito'], 'indice': d.get('indice'),
            'tutte': t, 'solo_validate': d['solo_validate']['casi_per_gradino'],
            'varianti': d['varianti'], 'principi': principi, 'fini': d.get('fini'), 'nuove': d.get('nuove'),
            # i casi citanti che fanno l'indice (11/10/2026, il PI: «si esplora?»): nome, gradino, peso, paese, citazione
            'casi_elenco': sorted(({'id': cid, 'nome': c['nome'], 'gradino': c['gradino'], 'peso': PESI_ATTESI[int(c['gradino'][1])],
                                    'giur': c['giurisdizione'], 'righe': c['righe'], 'documenti': c['documenti'],
                                    'codice': c['codice'] if c['codice'] in CODICI_PUBBLICI else ''}
                                   for cid, c in d['casi'].items()), key=lambda x: (-x['peso'], -x['righe'], x['nome'])),
        }
    return out


def scrivi_firestore(r, sito):
    """Le proprie schede, e solo quelle: trace_versioni/N01 e trace_misure/N01-<data>. corpus_rows non si tocca."""
    from google.cloud import firestore
    db = firestore.Client(project='climpact-drp')
    v = r['versione']
    giorno = v['calcolato_il'][:10]
    testo = json.dumps(sito, ensure_ascii=False)
    db.collection('trace_misure').document(f'N01-{giorno}').set({
        'titolo': f'N01, influenza (beta): misure del {giorno}', 'file': 'pubblicazione/influenza/n01_sito.json',
        'testo': testo, 'byte': len(testo.encode()), 'formato': 'json', 'regola': 'N01', 'versione': v['versione']})
    db.collection('trace_versioni').document('N01').set({
        'codice': 'N01', 'tipo': 'regola', 'nome': 'Influence of a judgment and of its principles (beta)',
        'compito': 'Scala di ricezione R1-R4 per caso citante; portata, mobilitazione, ricezione giudiziale; '
                   'principi; correzione per l errore di lettura; sensibilita con pesi che rispettano solo l ordine.',
        'data': giorno, 'stato': 'beta', 'casi': v['casi'],
        'codice_sorgente': [{'file': 'tools/n01_influenza.py', 'sha256': v['sha256_script']}],
        'parametri': [{'file': 'pubblicazione/influenza/n01_soglie.json', 'sha256': v['sha256_soglie']},
                      {'file': 'pubblicazione/influenza/n01_giurisdizioni.json', 'sha256': v['sha256_giurisdizioni']}],
        'regola': 'pubblicazione/influenza/METODO-INFLUENZA-BOZZA.md',
        'misure': f'trace_misure/N01-{giorno}',
        'righe': {k: d['righe_per_esito'] for k, d in r['decisioni'].items()},
        'modello': 'nessuno (deterministico)'})
    print('scritte trace_versioni/N01 e', f'trace_misure/N01-{giorno}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--casi', default=','.join(PREFISSI))
    ap.add_argument('--da-file')
    ap.add_argument('--uscita', default=str(CARTELLA / 'n01_misure.json'))
    ap.add_argument('--esiti', default='gs://climpact-drp.firebasestorage.app/site-content/data/trace-0.1/mappa/casi.json.gz',
                    help="il file dei casi della mappa (esito per chi ha agito, letto in automatico): percorso o gs://")
    ap.add_argument('--senza-usa', action='store_true',
                    help="toglie gli atti di corti statunitensi (filtro di sensibilita', 15/10/2026); le decisioni citate restano")
    ap.add_argument('--senza-controversie', action='store_true',
                    help="non unisce i casi di una stessa raccolta del database (il conto di prima del 15/10/2026)")
    ap.add_argument('--scrivi', action='store_true', help='scrive le schede N01 in trace_versioni e trace_misure')
    a = ap.parse_args()
    casi = [c.strip() for c in a.casi.split(',') if c.strip()]
    S = json.loads(SOGLIE.read_text())
    giur = Giur(json.loads(GIURISDIZIONI.read_text()))
    date_doc = json.loads(DATE_DOC.read_text()) if DATE_DOC.exists() else {}
    esiti = leggi_esiti(a.esiti)
    dati = leggi_file(a.da_file, casi) if a.da_file else leggi_firestore(casi)
    contr = json.loads(CONTROVERSIE.read_text()) if CONTROVERSIE.exists() and not a.senza_controversie else {}
    unite = unisci_controversie(dati, contr) if contr else {}
    if a.senza_usa:
        dati = {k: [x for x in v if giur(x.get('giurisdizioni')) != 'United States'] for k, v in dati.items()}
    r = calcola(dati, S, giur, date_doc, esiti)
    r['controversie_unite'] = unite
    r['versione'] = {'regola': 'N01', 'versione': S['versione'], 'calcolato_il': dt.datetime.now().isoformat(timespec='seconds'),
                     'casi': casi, 'sha256_script': sha(pathlib.Path(__file__)), 'sha256_soglie': sha(SOGLIE),
                     'sha256_giurisdizioni': sha(GIURISDIZIONI), 'fonte': a.da_file or 'firestore corpus_rows',
                     'controversie': {'file': CONTROVERSIE.name, 'sha256': sha(CONTROVERSIE), 'dump': contr.get('fonte')} if contr else None,
                     'filtro': 'senza atti di corti statunitensi' if a.senza_usa else None}
    pathlib.Path(a.uscita).write_text(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    sito = per_il_sito(r)
    pathlib.Path(a.uscita).with_name('n01_sito.json').write_text(json.dumps(sito, ensure_ascii=False, default=str))
    for k, v in r['decisioni'].items():
        print(k, v['righe_vive'], 'casi', v['tutte']['casi_per_gradino'], 'validate', v['righe_validate'])
    if a.scrivi:
        if a.senza_usa:
            sys.exit('--scrivi con --senza-usa no: le schede N01 sono quelle del conto con tutti gli atti')
        scrivi_firestore(r, sito)


if __name__ == '__main__':
    main()
