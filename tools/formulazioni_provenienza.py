"""PROVENIENZA DELLE FORMULAZIONI RICAVATE — da quale caso, da quale atto.

   RICHIESTA DEL PI (23/09/2026): ogni formulazione della terza famiglia deve
   dire da dove viene — caso, tipo di atto, pagina — e, per quelle ricavate,
   da quale testo vero sono state scritte. Senza, la pagina non si puo'
   controllare: il PI ha trovato una «concorrente» che secondo lui e' una
   ripresa, e per capirlo serviva risalire al giudizio umano che l'aveva
   bocciata.

   Le ancore sono di tre tipi (vedi `ancore_per_fable.json`):
     U  frase delle sentenze di Urgenda (canonical e seeds di urgenda.yaml);
     C  passaggio confermato dai validatori;
     R  passaggio bocciato dai validatori.
   Per U la provenienza sta nel file del caso (documento e pagina); per C e R
   si ritrova la riga giudicata nell'esportazione dei giudizi, confrontando il
   testo dell'ancora con la citazione validata.

   Scrive il campo `provenienza` dentro `formulazioni_derivate.json` e rigenera
   `formulazioni_derivate.html`.
"""
import html, json, pathlib, re
import yaml

QUI = pathlib.Path(__file__).resolve().parent.parent
T = QUI/'training'
GRADI = {
    'urgenda-foundation-v-state-of-the-netherlands-decision_f1ad': "Rechtbank Den Haag, sentenza di primo grado del 24 giugno 2015",
    'urgenda-foundation-v-state-of-the-netherlands-decision_8a5e': "Gerechtshof Den Haag, sentenza d'appello del 9 ottobre 2018",
    'urgenda-foundation-v-state-of-the-netherlands-judgment_ed17': "Hoge Raad, sentenza di cassazione del 20 dicembre 2019",
}
ESITI = {'confermata': 'confermata', 'scartata': 'scartata', 'riclassificata': 'riclassificata'}


def norm(s):
    s = re.sub(r'-\s+', '', s or '')
    return re.sub(r'[^a-z0-9àèéìòùäöüßç]+', ' ', s.lower()).strip()


def main():
    anc = json.loads((T/'ancore_per_fable.json').read_text(encoding='utf-8'))
    mappa = json.loads((T/'ancore_mappa_casi.json').read_text(encoding='utf-8'))
    der = json.loads((T/'formulazioni_derivate.json').read_text(encoding='utf-8'))
    giud = json.loads((QUI/'giudizi-umani-2026-09-22.json').read_text(encoding='utf-8'))
    y = yaml.safe_load((QUI/'cited-cases'/'urgenda.yaml').read_text(encoding='utf-8'))
    sonde = {s['id']: s for s in y['semantic_queries']}

    # frasi di Urgenda: canonical e seeds, con documento e pagina
    frasi_u = []
    for sid, s in sonde.items():
        if s.get('canonical'):
            frasi_u.append((norm(s['canonical']), s['canonical_documento'], s['canonical_pagina'], s.get('canonical_paragrafo')))
        for sd in s.get('seeds') or []:
            frasi_u.append((norm(sd['testo']), sd['documento'], sd['pagina'], sd.get('paragrafo')))

    def testi_riga(r):
        t = [r.get('validato_citazione_testuale'), r.get('proposto_citazione_testuale')]
        t += [h.get('campi', {}).get('validato_citazione_testuale') for h in r.get('_storia') or []]
        return [norm(x) for x in t if x]

    prov = {}
    for sid, blocco in anc.items():
        for gruppo in ('urgenda', 'confermati', 'bocciati'):
            for a in blocco[gruppo]:
                chiave = norm(a['testo'])[:160]
                if gruppo == 'urgenda':
                    m = next((f for f in frasi_u if chiave[:90] in f[0] or f[0][:90] in chiave), None)
                    prov[a['id']] = ({'origine': 'sentenza di Urgenda', 'caso': 'Urgenda Foundation c. Paesi Bassi',
                                      'atto': GRADI.get(m[1], m[1]), 'documento': m[1], 'pagina': m[2],
                                      'paragrafo': m[3]} if m else {'origine': 'sentenza di Urgenda', 'non_trovata': True})
                    continue
                caso = mappa.get(a['id'])
                cand = [r for r in giud if r['case_id'] == caso and any(chiave[:120] in t or t[:120] in chiave for t in testi_riga(r))]
                if not cand:
                    # ancore mascherate: il nome del caso e' sostituito da ⟦CASO_CITATO⟧,
                    # si cerca il pezzo piu' lungo fra una maschera e l'altra
                    pezzo = norm(max(a['testo'].split('⟦CASO_CITATO⟧'), key=len))[20:90]
                    cand = [r for r in giud if r['case_id'] == caso
                            and any(pezzo in t for t in testi_riga(r) + [norm(r.get('finestra_pagina'))])]
                if not cand:
                    prov[a['id']] = {'origine': 'passaggio ' + ('confermato' if gruppo == 'confermati' else 'bocciato'),
                                     'case_id': caso, 'non_trovata': True}
                    continue
                r = cand[0]
                prov[a['id']] = {
                    'origine': 'passaggio ' + ('confermato' if gruppo == 'confermati' else 'bocciato'),
                    'caso': r['case_name'], 'atto': r.get('tipo_atto') or '', 'documento': r['document_id'],
                    'pagina': r.get('validato_pagina') or r.get('proposto_pagina'),
                    'giurisdizione': (r.get('giurisdizioni') or '').replace(';', ', '),
                    'riga': r['_id'], 'esito_umano': r.get('esito'), 'motivo_scarto': r.get('motivo_scarto'),
                    'sonda_giudicata': r.get('sonda'), 'nota_umana': r.get('validato_note') or '',
                    'righe_uguali': len(cand)}

    mancanti = [k for k, v in prov.items() if v.get('non_trovata')]
    for sid, s in der.items():
        for parte in ('ripresa', 'concorrenti'):
            for f in s[parte]:
                f['provenienza'] = prov.get(f['ancora'], {'non_trovata': True})
    (T/'formulazioni_derivate.json').write_text(json.dumps(der, ensure_ascii=False, indent=1), encoding='utf-8')
    scrivi_html(der, sonde)
    print(f'ancore {len(prov)}, senza provenienza {len(mancanti)}: {mancanti}')


def riga_prov(p, tipo):
    e = html.escape
    if p.get('non_trovata'):
        return '<span class="a">provenienza non ritrovata</span>'
    dove = f"{e(p['caso'])}, {e(p['atto'])}" + (f", p. {p['pagina']}" if p.get('pagina') else '')
    if p.get('paragrafo'):
        dove += f", § {e(str(p['paragrafo']))}"
    verbo = 'presa da' if tipo == 'vera' else 'scritta a partire da'
    s = f'<span class="a"><b>{verbo}</b> {dove}'
    if p.get('giurisdizione'):
        s += f' <i>({e(p["giurisdizione"])})</i>'
    s += '</span>'
    if p.get('esito_umano'):
        giud = {'confermata': 'confermata', 'scartata': 'scartata', 'riclassificata': 'riclassificata, contata come no'}.get(p['esito_umano'], p['esito_umano'])
        s += f'<span class="g">giudizio umano: {e(giud)}'
        if p.get('motivo_scarto'):
            s += f' ({e(p["motivo_scarto"].replace("_", " "))})'
        if p.get('nota_umana'):
            s += f'. Nota: «{e(p["nota_umana"].strip())}»'
        s += f'<span class="rid">{e(p["riga"])}</span></span>'
    return s


def scrivi_html(der, sonde):
    e = html.escape
    css = """:root{--bg:#f7f7f5;--card:#fff;--ink:#1c2230;--ink2:#5b6475;--accent:#1f4e8c;--v:#2c6a3e;--vs:#e0efe4;--r:#855700;--rs:#f5ebd6;--gs:#f1f3f6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15181e;--card:#1e222a;--ink:#e6e8ec;--ink2:#a0a8b8;--accent:#8fb4ea;--v:#8fd0a2;--vs:#1f3528;--r:#e8c27a;--rs:#3a2f1a;--gs:#262b35}}
:root[data-theme="dark"]{--bg:#15181e;--card:#1e222a;--ink:#e6e8ec;--ink2:#a0a8b8;--accent:#8fb4ea;--v:#8fd0a2;--vs:#1f3528;--r:#e8c27a;--rs:#3a2f1a;--gs:#262b35}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,system-ui,"Segoe UI",sans-serif}
main{max-width:880px;margin:0 auto;padding:32px 16px 64px}h1{font-size:26px;margin:0 0 6px}.intro{color:var(--ink2);margin:0 0 28px}
section{background:var(--card);border-radius:16px;padding:24px 28px;margin:0 0 24px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
@media (max-width:600px){section{padding:18px 16px}}
h2{font-size:20px;margin:0}.id{font:13px ui-monospace,Menlo,monospace;color:var(--ink2);margin:4px 0 12px}
.prop{background:var(--gs);border-radius:12px;padding:12px 16px;margin:0 0 18px}h3{font-size:15px;color:var(--accent);margin:20px 0 8px}
h3 span{display:block;font-weight:400;color:var(--ink2);font-size:13px}ol{margin:0;padding-left:26px}li{margin:0 0 14px}
.t{display:inline-block;font:600 11px/1 system-ui;letter-spacing:.05em;text-transform:uppercase;padding:4px 7px;border-radius:999px;margin-right:6px}
.t-vera{background:var(--vs);color:var(--v)}.t-ricavata{background:var(--rs);color:var(--r)}
.a{display:block;font-size:13px;color:var(--ink2);margin-top:4px}.a b{font-weight:600;color:var(--ink)}
.g{display:block;font-size:13px;color:var(--ink2);background:var(--gs);border-radius:8px;padding:6px 10px;margin-top:6px}
.rid{display:block;font:11px ui-monospace,Menlo,monospace;margin-top:2px;overflow-wrap:anywhere}"""
    out = ['<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
           f'<title>Formulazioni dai testi veri</title><style>{css}</style></head><body><main>',
           '<h1>Formulazioni ricavate dai testi veri</h1><p class="intro">Terza famiglia di domande, scritta da Claude Fable 5.1 in una sessione separata a partire da testi veri: le frasi delle sentenze di Urgenda, e i passaggi confermati o bocciati dai validatori nelle sole righe di addestramento. «Vera» vuol dire presa alla lettera o quasi da un testo; «ricavata» vuol dire scritta a partire da quel testo. Sotto ogni frase: il caso, l\'atto e la pagina da cui nasce, e per i passaggi giudicati il giudizio umano con la sua nota.</p>']
    for sid, s in der.items():
        q = sonde.get(sid, {})
        out.append(f'<section><h2>{e(q.get("titolo", sid))}</h2><p class="id">{e(sid)}</p><p class="prop">{e(" ".join((q.get("testo") or "").split()))}</p>')
        for parte, tit, sott in (('ripresa', 'Formulazioni di ripresa', 'dalle frasi delle sentenze di Urgenda e dai passaggi confermati'),
                                 ('concorrenti', 'Formulazioni concorrenti', 'dai passaggi bocciati: stessa conclusione, altra fonte')):
            out.append(f'<h3>{tit} <span>{sott}</span></h3><ol>')
            for f in s[parte]:
                tipo = 'vera' if f['tipo'] == 'vera' else 'ricavata'
                out.append(f'<li><span class="t t-{tipo}">{tipo}</span> {e(f["testo"])}{riga_prov(f["provenienza"], tipo)}</li>')
            out.append('</ol>')
        out.append('</section>')
    out.append('</main></body></html>')
    (T/'formulazioni_derivate.html').write_text(''.join(out), encoding='utf-8')


if __name__ == '__main__':
    main()
