"""DeepSeek classifies lexical citation rows (citation type, speaker, proposition).

   Rationale. The lexical network finds the case name; finding it is trivial, the task is to CLASSIFY what the
   citation does. The model must read the context of the page, not the single line, so DeepSeek receives the
   citation page with the previous and next pages, the flagged passage marked, and the codebook definitions
   verbatim.

   Phases:
     prepara  local machine. From a READ-ONLY local export of the Firestore rows
              (`training/fase2/<caso>_corpus_rows_*.json`) and the markdown files: context, markup, validator
              labels.  -> training/lessicali_<caso>_righe.jsonl
     leggi    GPU server, DeepSeek served by vLLM. Two readings per row, reasoning enabled.
              --gruppo validate first (to measure agreement with human annotators), then non_validate.
              -> training/lessicali_<caso>_deepseek.jsonl  (resumes where it stopped)
     --etichetta v2  re-reading with a revised codebook (footnote rule), written to a separate file so the first
              reading remains available for comparison.
     misura   Agreement with validators on citation type (accuracy, Cohen's kappa, confusion matrix) and agreement
              between the two readings.  -> training/lessicali_<caso>_deepseek_misure.json

   Writes nothing to the platform: outputs are machine proposals; human judgments remain the reference.
"""
import argparse, collections, concurrent.futures as cf, datetime, json, pathlib, re, sys, threading, time
QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
T = QUI/'training'
RIGHE = T/'lessicali_urgenda_righe.jsonl'
USCITA = T/'lessicali_urgenda_deepseek.jsonl'
MISURE = T/'lessicali_urgenda_deepseek_misure.json'
MODELLO = 'DeepSeek-V4-Flash-0731'
PRIMA, DOPO, CENTRO = 7000, 7000, 14000    # max characters: previous page (tail), next page (head), citation page
INIZIO, FINE = '[[INIZIO DEL BRANO SEGNALATO]]', '[[FINE DEL BRANO SEGNALATO]]'


# ── prepara (local machine) ──────────────────────────────────────────────

NOMI_BREVI = {'urgenda': 'Urgenda', 'neubauer': 'Neubauer', 'future-generations': 'Future Generations'}


def contesto(file, cs, forma, testuale, nome_re=re.compile(r'urgenda', re.I)):
    import build_chunks as B
    p = QUI/file
    testo = p.read_text(encoding='utf-8', errors='replace')
    meta, corpo, base = B.leggi(p)
    marks = [(a + base, n) for a, n in B.pagine(corpo)]
    # The name is at char_start; the passage flagged by the lexical network is the ~200-character context around
    # the name (proposto_citazione_testuale): it is located in the file, otherwise a fixed window is used.
    fo = forma if testo[cs:cs+len(forma)] == forma else ''
    if not fo:
        m = nome_re.search(testo, max(0, cs-50), cs+300)
        cs, fo = (m.start(), m.group(0)) if m else (cs, '')
    q0 = testo.find(testuale[:60], max(0, cs-600), cs+600) if testuale else -1
    b_da, b_a = (q0, q0 + len(testuale)) if q0 >= 0 else (max(0, cs-200), cs+250)
    b_da, b_a = min(b_da, cs), max(b_a, cs + len(fo))
    if marks:
        confini = marks + [(len(testo), None)]
        k = max([i for i, (a, _) in enumerate(marks) if a <= cs] or [0])
        pag = marks[k][1]
        da_p, a_p = marks[k][0], confini[k+1][0]
        prec = (marks[k-1][0], marks[k][0]) if k > 0 else None
        succ = (confini[k+1][0], confini[k+2][0]) if k + 1 < len(marks) else None
    else:
        pag, da_p, a_p, prec, succ = None, base, len(testo), None, None
    # the citation page, trimmed around the passage if very long (documents without page markers)
    if a_p - da_p > CENTRO:
        da_p = max(da_p, cs - CENTRO//2); a_p = min(a_p, da_p + CENTRO)
    # the flagged passage may cross a page marker: the central part is extended to contain it entirely
    if b_a > a_p:
        a_p = b_a; succ = (b_a, succ[1]) if succ and succ[1] > b_a else None
    if b_da < da_p:
        da_p = b_da; prec = (prec[0], b_da) if prec and b_da > prec[0] else None
    centro = (testo[da_p:b_da] + INIZIO + testo[b_da:cs] + '⟦' + testo[cs:cs+len(fo)] + '⟧'
              + testo[cs+len(fo):b_a] + FINE + testo[b_a:a_p]) if da_p <= b_da and b_a <= a_p else testo[da_p:a_p]
    pezzi = []
    if prec:
        pezzi.append(('prima', testo[prec[0]:prec[1]][-PRIMA:]))
    pezzi.append(('citazione', centro))
    if succ:
        pezzi.append(('dopo', testo[succ[0]:succ[1]][:DOPO]))
    pulisci = lambda t: re.sub(r'<!--\s*page\s+(\d+)\s*-->', r'[pagina \1]', t)
    titolo = {'prima': 'PAGINA PRECEDENTE (fine)', 'citazione': 'PAGINA DELLA CITAZIONE', 'dopo': 'PAGINA SUCCESSIVA (inizio)'}
    return pag, '\n\n'.join(f'===== {titolo[k]} =====\n{pulisci(t).strip()}' for k, t in pezzi), bool(fo)


def prepara(righe_fs, caso='urgenda'):
    import yaml
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    forme = sorted({str(f) for f in conf['forme'] if len(str(f)) >= 4}, key=len, reverse=True)
    nome_re = re.compile('|'.join(re.escape(f) for f in forme), re.I) if caso != 'urgenda' else re.compile(r'urgenda', re.I)
    breve = NOMI_BREVI.get(caso, caso)
    fs = json.load(open(righe_fs, encoding='utf-8'))
    L = [x for x in fs if x.get('proposto_rete') in ('lessicale', 'entrambe')]
    n = collections.Counter()
    with open(RIGHE, 'w', encoding='utf-8') as f:
        for x in L:
            if not (QUI/x['file']).exists():
                n['senza_file'] += 1; continue
            pag, ctx, trovato = contesto(x['file'], int(x['char_start']), x.get('proposto_forma_trovata') or breve,
                                        x.get('proposto_citazione_testuale') or '', nome_re)
            n['nome_ritrovato' if trovato else 'nome_non_ritrovato'] += 1
            f.write(json.dumps({
                'id': x['_id'], 'document_id': x['document_id'], 'case_id': x['case_id'], 'case_name': x.get('case_name'),
                'tipo_atto': x.get('tipo_atto'), 'data': str(x.get('data') or '')[:10], 'pagina': pag,
                'proposto_rete': x['proposto_rete'], 'forma': x.get('proposto_forma_trovata'),
                'gruppo': 'validate' if x.get('esito') else 'non_validate',
                'umano': {k: x.get(k) for k in ('esito', 'validato_tipo_citazione', 'validato_chi_parla', 'validato_proposizione',
                                                  'motivo_scarto', 'validato_note')} if x.get('esito') else None,
                'contesto': ctx}, ensure_ascii=False) + '\n')
            n[x.get('esito') and 'validate' or 'non_validate'] += 1
    print(dict(n), '->', RIGHE)


# ── prompt ───────────────────────────────────────────────────────────────

def codebook():
    import yaml
    cb = yaml.safe_load(open(QUI/'codebook'/'citazioni.yaml', encoding='utf-8'))
    tipi = '\n'.join(f'- "{t["codice"]}" ({t["nome"]}): {" ".join(t["definizione"].split())} Indizi: {"; ".join(t.get("indizi") or [])}.'
                     for t in cb['tipo_citazione'])
    chi = '\n'.join(f'- "{c["codice"]}": {c["nome"]}' for c in cb['chi_parla'])
    limiti = '\n'.join(f'- {" ".join(c["questione"].split())} Regola: {" ".join(str(c["regola"]).split())}'
                       for c in cb['casi_limite'])
    return cb, tipi, chi, limiti


MODULO = """Sei un giurista che codifica citazioni giurisprudenziali per una ricerca sul contenzioso climatico.
Il caso citato e' URGENDA: Stichting Urgenda c. Stato dei Paesi Bassi (Rechtbank Den Haag 24/6/2015,
Gerechtshof Den Haag 9/10/2018, Hoge Raad 20/12/2019). Chi cita uno qualunque dei tre gradi cita Urgenda.

Qui sotto trovi il FASCICOLO del caso, scritto per il gruppo di ricerca: serve solo a sapere che cosa ha deciso
Urgenda e con quali paragrafi. Le domande di questo compito NON sono quelle del fascicolo: sono quelle in fondo.

{fascicolo}

========== FINE DEL FASCICOLO ==========

CODEBOOK DEL PROGETTO (versione {versione}). Categorie del TIPO DI CITAZIONE, esclusive (una sola per brano):
{tipi}

CHI PARLA (chi enuncia il brano):
{chi}

Casi limite e regole del codebook:
{limiti}

DOCUMENTO: {case_name} ({tipo_atto}, {data}), documento {document_id}.
La rete lessicale ha trovato il nome «{forma}» nel punto marcato con ⟦ ⟧, dentro il brano racchiuso fra
{inizio} e {fine}. Ti do la pagina della citazione con la fine della pagina precedente e l'inizio della
successiva. LEGGILE PER INTERO, note comprese: il ragionamento comincia prima del brano e finisce dopo, e
solo il contesto dice che cosa il testo fa di Urgenda e chi sta parlando (la corte, una parte che la corte
riassume, un amicus...).
---
{contesto}
---

Rispondi SOLO con un oggetto JSON con questi campi, in quest'ordine:
1. "riferimento": che cosa e' «{forma}» in questo punto. Uno fra: "caso_urgenda" (il caso o una delle sue
   pronunce), "fondazione_urgenda" (la fondazione come soggetto, non la sentenza: per esempio parte in un
   altro giudizio), "indice_o_elenco" (indice, tavola delle fonti, bibliografia, intestazione, elenco senza
   testo), "omonimo" (altro significato della parola), "non_determinabile".
2. "tipo_citazione": ESATTAMENTE UNO dei codici del codebook: "menzione_in_catena", "descrittiva",
   "sostanziale", "distinguente", "critica", "implicita". Anche se "riferimento" non e' "caso_urgenda",
   scegli la categoria piu' vicina (di solito "menzione_in_catena").
3. "chi_parla": uno dei codici di CHI PARLA: "corte", "parte", "interveniente", "amicus", "non_determinabile".
4. "proposizione": UNA frase in italiano: la proposizione che il brano attribuisce a Urgenda o ne trae
   (che cosa il testo dice che Urgenda ha stabilito, o che cosa ne ricava). Stringa vuota se non ce n'e'.
5. "paragrafi_urgenda": numeri di paragrafo di Urgenda citati nel brano, lista (vuota se nessuno).
6. "motivo": una frase, massimo trenta parole, che giustifica tipo e chi parla col contesto.

Niente fuori dal JSON."""


def modulo(caso):
    """Return the prompt template for a case. For Urgenda the original template is kept unchanged, so earlier
    readings remain comparable. For other cases the Urgenda-specific lines become generic, and the
    "soggetto_omonimo" referent covers a person or party bearing the case name (needed e.g. for Neubauer, which
    is also the name of an activist)."""
    if caso == 'urgenda':
        return MODULO
    import yaml
    conf = yaml.safe_load(open(QUI/'cited-cases'/f'{caso}.yaml', encoding='utf-8'))
    breve = NOMI_BREVI.get(caso, caso)
    m = MODULO.replace(
        "Il caso citato e' URGENDA: Stichting Urgenda c. Stato dei Paesi Bassi (Rechtbank Den Haag 24/6/2015,\n"
        "Gerechtshof Den Haag 9/10/2018, Hoge Raad 20/12/2019). Chi cita uno qualunque dei tre gradi cita Urgenda.",
        f"Il caso citato e' {conf.get('nome')} (decisione del {conf.get('data_decisione')}).")
    m = m.replace('"caso_urgenda" (il caso o una delle sue\n   pronunce), "fondazione_urgenda" (la fondazione come soggetto, non la sentenza: per esempio parte in un\n   altro giudizio)',
                  f'"caso" (il caso o una delle sue\n   pronunce), "soggetto_omonimo" (la persona, la parte o l\'organizzazione che porta il nome, non la sentenza: per esempio\n   un\'attivista o una parte in un altro giudizio)')
    m = m.replace('"caso_urgenda"', '"caso"').replace('paragrafi_urgenda', 'paragrafi_caso').replace('Urgenda', breve)
    return m


def prompt(r, fascicolo, cb, caso='urgenda'):
    _, tipi, chi, limiti = cb
    return modulo(caso).format(fascicolo=fascicolo, versione=cb[0]['versione'], tipi=tipi, chi=chi, limiti=limiti,
                         case_name=r.get('case_name') or r['case_id'], tipo_atto=r.get('tipo_atto') or 'atto',
                         data=r.get('data') or 's.d.', document_id=r['document_id'], forma=r.get('forma') or NOMI_BREVI.get(caso, caso),
                         inizio=INIZIO, fine=FINE, contesto=r['contesto'])


# ── response parsing ─────────────────────────────────────────────────────

CAMPI = ('riferimento', 'tipo_citazione', 'chi_parla', 'proposizione', 'motivo')


def estrai_tollerante(testo):
    """Parse a model answer tolerantly. DeepSeek's JSON breaks when the proposition contains unescaped quotes
    (12 of 684 readings on validated rows). The JSON is tried first; if it fails, fields are extracted one by
    one. A recovered reading is marked with `recuperata`."""
    from adjudica_llm import estrai
    g = estrai(testo)
    if g.get('esito') != 'ILLEGGIBILE':
        return g
    grezzo = g.get('grezzo') or testo or ''
    r = {k: m.group(1) for k in CAMPI for m in [re.search(rf'"{k}"\s*:\s*"([^"]*)"', grezzo)] if m}
    return {**r, 'recuperata': True, 'grezzo': grezzo[:2000]} if r.get('tipo_citazione') else g


def accordi(x):
    g = x['letture']
    for k, c in (('tipo', 'tipo_citazione'), ('chi_parla', 'chi_parla'), ('riferimento', 'riferimento')):
        v = [y.get(c) for y in g]
        x[f'accordo_{k}'] = len(g) > 1 and len(set(v)) == 1 and v[0] is not None
    return x


# ── leggi (GPU server) ───────────────────────────────────────────────────

def leggi(a):
    from openai import OpenAI
    cli = OpenAI(api_key=pathlib.Path(a.chiave_file).read_text().strip(), base_url=a.base_url, timeout=1800)
    fascicolo = (QUI/'cited-cases'/f'{a.caso}-fascicolo.md').read_text(encoding='utf-8')
    cb = codebook()
    righe = [json.loads(l) for l in open(RIGHE, encoding='utf-8')]
    righe = [r for r in righe if a.gruppo in ('tutte', r['gruppo'])]
    # Optional subset of rows (e.g. rows added by the corrected search S02, or rows whose reading was unparseable):
    # a file with one row id per line.
    if a.solo_id:
        tenere = set(pathlib.Path(a.solo_id).read_text(encoding='utf-8').split())
        righe = [r for r in righe if r['id'] in tenere]
    if a.max_righe:
        righe = righe[:a.max_righe]
    fatte = {json.loads(l)['id'] for l in open(USCITA, encoding='utf-8')} if USCITA.exists() else set()
    da_fare = [r for r in righe if r['id'] not in fatte]
    print(f'{a.gruppo}: {len(righe)} righe, {len(fatte)} gia\' fatte in tutto, {len(da_fare)} da fare', flush=True)
    blocco = threading.Lock()

    def chiama(testo):
        ultimo = ''
        for tentativo in range(5):
            try:
                corpo = ({'chat_template_kwargs': json.loads(a.kwargs_modello)} if a.kwargs_modello
                         else {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': a.sforzo}})
                r = cli.chat.completions.create(model=a.modello, messages=[{'role': 'user', 'content': testo}], max_tokens=8000,
                                                extra_body=corpo)
                m = r.choices[0].message
                return {'testo': m.content or '', 'ragionamento': getattr(m, 'reasoning_content', '') or '', 'token': r.usage.completion_tokens}
            except Exception as e:
                time.sleep(5 * (tentativo + 1)); ultimo = repr(e)[:200]
        return {'testo': '', 'errore': ultimo, 'token': 0}

    def una(r):
        testo = prompt(r, fascicolo, cb, a.caso)
        lett = [chiama(testo) for _ in range(a.letture)]
        g = [estrai_tollerante(x['testo']) for x in lett]
        return accordi({'id': r['id'], 'modello': MODELLO, 'data': datetime.date.today().isoformat(), 'gruppo': r['gruppo'],
                        'letture': g, 'ragionamenti': [x['ragionamento'][:4000] for x in lett], 'token': [x['token'] for x in lett]})

    t0 = time.time()
    with cf.ThreadPoolExecutor(a.paralleli) as ex, open(USCITA, 'a', encoding='utf-8') as f:
        for n, e in enumerate(ex.map(una, da_fare), 1):
            with blocco:
                f.write(json.dumps(e, ensure_ascii=False) + '\n'); f.flush()
            if n % 20 == 0:
                print(f'  {n}/{len(da_fare)} [{time.time()-t0:.0f}s]', flush=True)
    print(f'fatto in {time.time()-t0:.0f}s', flush=True)


# ── misura ───────────────────────────────────────────────────────────────

def kappa(a, b):
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb_ = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb_[k] for k in set(ca) | set(cb_)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else None


def misura():
    righe = {json.loads(l)['id']: json.loads(l) for l in open(RIGHE, encoding='utf-8')}
    ds = [json.loads(l) for l in open(USCITA, encoding='utf-8')]
    for x in ds:     # readings unparseable before the tolerant parser are recovered from the stored raw text
        x['letture'] = [estrai_tollerante(g.get('grezzo', '')) if g.get('esito') == 'ILLEGGIBILE' else g for g in x['letture']]
        accordi(x)
    CAT = ['menzione_in_catena', 'descrittiva', 'sostanziale', 'distinguente', 'critica', 'implicita']
    out = {'modello': MODELLO, 'data': datetime.date.today().isoformat(), 'righe_lette': len(ds),
           'per_gruppo': dict(collections.Counter(x['gruppo'] for x in ds))}
    tipo = lambda g: g.get('tipo_citazione') if g.get('tipo_citazione') in CAT else 'illeggibile'
    out['letture_illeggibili'] = sum(tipo(g) == 'illeggibile' for x in ds for g in x['letture'])
    out['letture_recuperate_dal_testo'] = sum(bool(g.get('recuperata')) for x in ds for g in x['letture'])
    out['accordo_fra_letture'] = {
        k: {'righe': len(ds), 'uguali': sum(x[f'accordo_{k}'] for x in ds),
            'quota': round(sum(x[f'accordo_{k}'] for x in ds) / max(len(ds), 1), 3)} for k in ('tipo', 'chi_parla', 'riferimento')}
    out['kappa_fra_letture_tipo'] = kappa([tipo(x['letture'][0]) for x in ds if len(x['letture']) > 1],
                                          [tipo(x['letture'][1]) for x in ds if len(x['letture']) > 1])
    V = [(x, righe[x['id']]['umano']) for x in ds if x['gruppo'] == 'validate' and (righe[x['id']]['umano'] or {}).get('validato_tipo_citazione')]
    if V:
        um = [u['validato_tipo_citazione'] for _, u in V]
        m = {}
        for i in range(len(V[0][0]['letture'])):
            dsi = [tipo(x['letture'][i]) if i < len(x['letture']) else 'illeggibile' for x, _ in V]
            m[f'lettura_{i+1}'] = {'righe': len(V), 'accuratezza': round(sum(p == q for p, q in zip(um, dsi)) / len(V), 3),
                                    'kappa': round(kappa(um, dsi), 3)}
        acc = [(x, u) for x, u in V if x['accordo_tipo']]
        um_a = [u['validato_tipo_citazione'] for _, u in acc]; ds_a = [tipo(x['letture'][0]) for x, _ in acc]
        m['letture_concordi'] = {'righe': len(acc), 'copertura': round(len(acc) / len(V), 3),
                                 'accuratezza': round(sum(p == q for p, q in zip(um_a, ds_a)) / max(len(acc), 1), 3),
                                 'kappa': round(kappa(um_a, ds_a), 3) if acc else None}
        conf = collections.defaultdict(collections.Counter)
        for (x, u) in V:
            conf[u['validato_tipo_citazione']][tipo(x['letture'][0])] += 1
        m['confusione_lettura_1'] = {'righe=validatori, colonne=DeepSeek': {k: dict(v) for k, v in sorted(conf.items())}}
        # substantive vs. rest: the distinction that matters most for the research question
        bs = [(u == 'sostanziale', tipo(x['letture'][0]) == 'sostanziale') for (x, _), u in zip(V, um)]
        tp = sum(a and b for a, b in bs); fp = sum(b and not a for a, b in bs); fn = sum(a and not b for a, b in bs)
        m['sostanziale_contro_resto_lettura_1'] = {'precisione': round(tp / max(tp + fp, 1), 3), 'richiamo': round(tp / max(tp + fn, 1), 3),
                                                  'kappa': round(kappa([a for a, _ in bs], [b for _, b in bs]), 3)}
        cp = [(u.get('validato_chi_parla'), x['letture'][0].get('chi_parla')) for x, u in V if u.get('validato_chi_parla')]
        m['chi_parla_lettura_1'] = {'righe': len(cp), 'accuratezza': round(sum(a == b for a, b in cp) / max(len(cp), 1), 3),
                                    'kappa': round(kappa([a for a, _ in cp], [b for _, b in cp]), 3) if cp else None}
        out['accordo_con_i_validatori'] = m
    sc = [(x, righe[x['id']]['umano']) for x in ds if (righe[x['id']]['umano'] or {}).get('esito') == 'scartata']
    out['righe_scartate_dai_validatori'] = [{'id': x['id'], 'riferimento': [g.get('riferimento') for g in x['letture']],
                                            'motivo_scarto': u.get('motivo_scarto')} for x, u in sc]
    NV = [x for x in ds if x['gruppo'] == 'non_validate']
    if NV:
        out['non_validate'] = {
            'righe': len(NV),
            'tipo_lettura_1': dict(collections.Counter(tipo(x['letture'][0]) for x in NV)),
            'tipo_concorde': dict(collections.Counter(tipo(x['letture'][0]) if x['accordo_tipo'] else 'letture_discordi' for x in NV)),
            'riferimento_lettura_1': dict(collections.Counter(x['letture'][0].get('riferimento') for x in NV)),
            'chi_parla_lettura_1': dict(collections.Counter(x['letture'][0].get('chi_parla') for x in NV))}
    MISURE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('fase', choices=['prepara', 'leggi', 'misura'])
    ap.add_argument('--caso', default='urgenda')
    ap.add_argument('--kwargs-modello', default='', help="JSON per chat_template_kwargs di un modello diverso da DeepSeek (es. GLM)")
    ap.add_argument('--righe-firestore', default='')
    ap.add_argument('--gruppo', default='validate', choices=['validate', 'non_validate', 'tutte'])
    ap.add_argument('--letture', type=int, default=2)
    ap.add_argument('--sforzo', default='low', help='stesso ragionamento del lettore misurato')
    ap.add_argument('--paralleli', type=int, default=48)
    ap.add_argument('--max-righe', type=int, default=0)
    ap.add_argument('--modello', default='deepseek-v4-flash')
    ap.add_argument('--base-url', default='http://127.0.0.1:8000/v1')
    ap.add_argument('--chiave-file', default=str(QUI/'chat'/'chiave'))
    ap.add_argument('--etichetta', default='', help="seconda lettura con un codebook cambiato: file a parte, la prima resta com'e'")
    ap.add_argument('--solo-id', default='', help='file con gli identificativi delle righe da leggere (una per riga)')
    a = ap.parse_args()
    RIGHE = T/f'lessicali_{a.caso}_righe.jsonl'
    USCITA = T/f'lessicali_{a.caso}_deepseek{"_" + a.etichetta if a.etichetta else ""}.jsonl'
    MISURE = T/f'lessicali_{a.caso}_deepseek{"_" + a.etichetta if a.etichetta else ""}_misure.json'
    if not a.righe_firestore:
        a.righe_firestore = str(T/'fase2'/'urgenda_corpus_rows_2026-09-26.json') if a.caso == 'urgenda' else str(T/'fase2'/f'{a.caso}_corpus_rows_2026-09-28.json')
    prepara(a.righe_firestore, a.caso) if a.fase == 'prepara' else leggi(a) if a.fase == 'leggi' else misura()
