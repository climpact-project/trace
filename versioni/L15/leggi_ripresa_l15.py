"""L15, LA DOMANDA NUOVA SULLA RIPRESA IMPLICITA, A PASSI E COL FASCICOLO DEL CASO (10/10/2026, S09, in prova).

Perche': con L14 (tools/leggi_ripresa_l14.py) DeepSeek dice «si» quando la finestra e il paragrafo hanno lo stesso TEMA ma non la
stessa PROPOSIZIONE (effetto serra contro Neubauer sull'IPCC, asma di un giovane contro le ricorrenti di KlimaSeniorinnen, Hansen che
scrive le stesse cose in due cause, un argomento di attribuzione contro la CIG). La domanda di L14 lo dice gia' («il tema non basta»)
e DeepSeek lo ignora: 9,8% di falsi positivi sui 163 negativi della taratura (regola A), limite 5%.

L15 fa ragionare in passi PRIMA della risposta e mette nella domanda il FASCICOLO DEL CASO, lo stesso di L05
(cited-cases/<caso>-fascicolo.md, come tools/classifica_lessicali.py e tools/cinque_letture.py): principi con definizioni, elementi
distintivi, fonti concorrenti, falsi amici, casi che contano e casi che non contano. I passi:
  1 la proposizione SPECIFICA del paragrafo in una frase, confrontata coi principi e le definizioni del fascicolo
  2 distintiva o luogo comune SECONDO IL FASCICOLO (scienza IPCC, diritti generici, trattati): luogo comune -> NO
  3 la frase della finestra che afferma la stessa proposizione, copiata alla lettera
  4 fonti alternative: la finestra attribuisce l'idea a qualcun altro (esperto, IPCC, altra corte, legge)? -> NO o FORSE
  5 cronologia: l'atto puo' essere anteriore alla decisione? -> NO (la data dell'atto, quando c'e', e' nella domanda)
  6 solo allora l'esito, in un JSON strutturato

Stesso schema di lettura di L14: cinque letture DeepSeek, ragionamento alto, tetto 24.000 token; stesse 249 coppie della taratura,
stesso freno 1, freni 2-4 di freni.py sulla frase della finestra; in piu' il freno di COERENZA (scritto prima delle letture): una
lettura «si» che dice «distintiva: no», o che nomina una fonte alternativa, o una cronologia incompatibile, e' scartata.
Regola di decisione: training/misure/PONTE-L15-DOMANDA-NUOVA-2026-10-10.md (scritta prima delle letture).

    python tools/leggi_ripresa_l15.py prepara            # Mac: richieste prova (3), taratura (249), esempi (12), pool (3.228)
    python tools/leggi_ripresa_l15.py secco --richieste R.jsonl.gz --tokenizer T
    python tools/leggi_ripresa_l15.py prova-freni
    python tools/leggi_ripresa_l15.py leggi ...          # ReCaS, come L14 (codice L15 negli esiti)
    python tools/leggi_ripresa_l15.py raccogli --richieste R --esiti E --uscita U

Niente e' scritto in banca dati.
"""
import argparse
import collections
import gzip
import hashlib
import json
import pathlib
import re
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI / 'tools'))
import freni  # noqa: E402
import leggi_coppia_l13 as L13  # noqa: E402
import leggi_ripresa_l14 as L14  # noqa: E402

CODICE = 'L15'
LETTURE_DS = 5
TETTO_DS = 24000
ESITI = ('si', 'no', 'forse')
FINESTRA_MAX_TOKEN = 120000     # dossier + paragrafo + finestra entro il contesto del server (131.072) meno il tetto: vedi `secco`

MODULO = """Sei un giurista che cerca le RIPRESE IMPLICITE di una sentenza climatica negli atti successivi.
La decisione e' {nome_caso} (del {data_caso}). Una ricerca per nome non l'ha trovata nell'atto qui sotto: l'atto non la nomina.

FASCICOLO DEL CASO. E' il materiale di riferimento su questa decisione: i suoi principi con le definizioni, gli elementi
distintivi, le fonti concorrenti che dicono cose simili, i falsi amici, i casi che contano come ripresa e quelli che non contano.
Usalo nei passi 1, 2 e 4.
=== INIZIO FASCICOLO ===
{fascicolo}
=== FINE FASCICOLO ===

PARAGRAFO DELLA DECISIONE: {etichetta}.
Sintesi della mappa dei paragrafi (scritta da noi, non e' testo della decisione): {sintesi}
{verbatim}Principi che la mappa attribuisce a questo paragrafo:
{principi}
Testo del paragrafo (il passo della decisione piu' vicino alla pagina dell'atto):
---
{passo}
---

PAGINA DELL'ATTO: {titolo} ({tipo_atto}), documento {document_id}{lingua}, pagina {pagina}.
Data dell'atto: {data_atto}
Qui sotto una finestra di circa 1.200 caratteri di quella pagina, estratta dal PDF: puo' avere righe spezzate, refusi, note a pie'
di pagina mescolate al testo; il nome della decisione e i numeri dei paragrafi possono mancare.
---
{finestra}
---

DOMANDA. La finestra RIPRENDE il paragrafo, cioe' usa la proposizione PROPRIA di questa decisione senza nominarla?
Una ripresa implicita si riconosce solo da cio' che questa decisione dice e le altre fonti non dicono. Ragiona in questi passi,
nell'ordine, prima di rispondere:

1. PROPOSIZIONE SPECIFICA. Scrivi in una frase che cosa dice questo paragrafo che le altre fonti non dicono: la regola, il criterio,
   la formula o la conseguenza propria di questa decisione. Confrontala con i principi e le loro definizioni nel fascicolo: se il
   paragrafo corrisponde a un principio, usa quella definizione; se il paragrafo racconta solo fatti, scienza o norme, dillo.
2. DISTINTIVA O LUOGO COMUNE. Secondo il fascicolo (elementi distintivi, fonti concorrenti, falsi amici), la proposizione e' propria
   di questa decisione o e' un luogo comune che si trova anche altrove: scienza del clima e rapporti IPCC, effetti del riscaldamento
   sulla salute o sugli ecosistemi, diritti umani in generale, testi e storia dei trattati (UNFCCC, Kyoto, Parigi, Montreal),
   bilancio di carbonio, urgenza di ridurre? Se e' un luogo comune, da questa finestra non si puo' riconoscere una ripresa di
   QUESTA decisione: la risposta e' NO.
3. FRASE DELLA FINESTRA. Trova nella finestra la frase che afferma la STESSA proposizione specifica del passo 1 (non lo stesso tema)
   e copiala alla lettera, nella sua lingua. Se non c'e', la risposta e' NO.
4. FONTI ALTERNATIVE. La finestra attribuisce l'idea a qualcun altro (un esperto, l'IPCC o un altro rapporto scientifico, un'altra
   corte o un'altra decisione, una legge, un trattato), o la stessa idea viene da una fonte comune che anche la decisione usa (lo
   stesso perito, lo stesso rapporto)? Il fascicolo elenca le fonti concorrenti. Se si', la risposta e' NO, o FORSE se la
   formulazione resta propria di questa decisione.
5. CRONOLOGIA. Se la data dell'atto e' anteriore alla data della decisione, l'atto non puo' riprenderla: la risposta e' NO. Se la
   data non e' nota, guarda se la finestra parla di fatti successivi o anteriori alla decisione.
6. Solo ora l'esito:
   SI: la proposizione e' distintiva, la finestra la afferma, la applica o argomenta da essa (anche con altre parole o in un'altra
   lingua), nessuna fonte alternativa la spiega, la cronologia e' compatibile.
   NO: luogo comune, solo il tema in comune, un'altra proposizione, un'altra fonte, cronologia incompatibile, un indice, una
   bibliografia, un testo rotto; oppure la finestra nomina la decisione stessa (scrivilo nel motivo: non e' implicita).
   FORSE: la proposizione e' distintiva e compatibile, ma la finestra non basta per deciderlo.
   Se non sei sicuro scegli FORSE, non SI.

Rispondi SOLO con un oggetto JSON, con i campi in quest'ordine:
{{"proposizione_specifica": "passo 1, una frase", "principio": "l'id del principio del fascicolo a cui corrisponde, o vuoto", "distintiva": "si" | "no", "frase_finestra": "passo 3: la frase della FINESTRA COPIATA ALLA LETTERA nella sua lingua, massimo 60 parole; vuota se non c'e'", "fonte_alternativa": "passo 4: la fonte a cui la finestra attribuisce l'idea; vuoto se nessuna", "cronologia": "compatibile" | "incompatibile" | "non nota", "esito": "si" | "no" | "forse", "motivo": "una frase, massimo quaranta parole"}}
Niente fuori dal JSON."""

NESSUNA = re.compile(r'^\W*(nessun[ao]?|none|no|n/?a|null|vuot[oa]|-+)?\W*$', re.I)


def fascicolo(caso):
    """il fascicolo di L05: cited-cases/<caso>-fascicolo.md (come classifica_lessicali.py e cinque_letture.py)"""
    return (QUI / 'cited-cases' / f'{caso}-fascicolo.md').read_text(encoding='utf-8')


def data_atto(meta):
    """la data dell'atto: quella del file nella pagina di origine (…/AAAAMMGG_…), che e' la data del documento; altrimenti si dice
    che non e' nota. `data_deposito` del front matter NON si usa: e' la data della causa, non dell'atto (Multnomah: 2023 la causa,
    20260615 il documento)"""
    m = re.search(r'/((?:19|20)\d{2})(\d{2})(\d{2})[_-]', meta.get('url_origine', '') or '')
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)} (dalla pagina di origine del documento)'
    anno = meta.get('anno_avvio') or ''
    return f"non nota (la causa e' iniziata nel {anno}; l'atto puo' essere successivo)" if anno else 'non nota'


class DomandaL15(L14.DomandaL14):
    def __init__(self, voci, atti, prove=None):
        super().__init__(voci, atti, prove)
        self._fasc = {}

    def fascicolo(self, caso):
        if caso not in self._fasc:
            self._fasc[caso] = fascicolo(caso)
        return self._fasc[caso]

    def testo(self, c, rr=False, finestra=None):
        s = self.voci.scheda(c['voce'])
        doc, pagina = L14.doc_e_pagina(c['pid'], self.prove)
        meta = self.atti.meta(doc)
        lingua = f", lingua {meta['lingue']}" if meta.get('lingue') else ''
        verbatim = f"Frase caratteristica del paragrafo: «{s['verbatim']}»\n" if s['verbatim'] else ''
        return MODULO.format(nome_caso=s['nome_caso'], data_caso=s['data_caso'], fascicolo=self.fascicolo(s['caso']).strip(),
                             etichetta=s['etichetta'], sintesi=s['sintesi'] or '(nessuna)', verbatim=verbatim,
                             principi=self._principi(s), passo=c['d'].strip(),
                             titolo=meta.get('document_title') or meta.get('case_name') or doc,
                             tipo_atto=meta.get('tipo_atto') or 'atto', document_id=doc, lingua=lingua,
                             pagina=pagina or 'non nota', data_atto=data_atto(meta),
                             finestra=(finestra if finestra is not None else c['q']).strip())

    @staticmethod
    def testi_prompt():
        return [MODULO]


class FreniL15:
    """Freni 2-4 (freni.py) sulla `frase_finestra`, come L14 sulla `frase`; in piu' il freno di COERENZA, scritto prima delle letture:
    un «si» con «distintiva: no», con una fonte alternativa nominata o con cronologia «incompatibile» contraddice i passi della
    domanda e la lettura e' scartata. Il fascicolo sta nel prompt: una frase copiata dal fascicolo e non dalla finestra e' inventata."""

    def __init__(self, puro, testi_prompt):
        self.f14 = L14.FreniL14(puro, testi_prompt)

    def verifica(self, j):
        if not isinstance(j, dict) or j.get('esito') not in ESITI:
            return False, 'risposta senza esito valido', {}
        j14 = {'esito': j['esito'], 'frase': j.get('frase_finestra', j.get('frase', '')), 'motivo': j.get('motivo', '')}
        ok, motivo, det = self.f14.verifica(j14)
        if not ok:
            return ok, motivo, det
        if j['esito'] == 'si':
            if str(j.get('distintiva', '')).strip().lower() not in ('si', 'sì', 'yes'):
                return False, 'incoerente: si su un luogo comune', det
            if not NESSUNA.match(str(j.get('fonte_alternativa') or '')):
                return False, 'incoerente: si con una fonte alternativa', det
            if str(j.get('cronologia', '')).strip().lower() == 'incompatibile':
                return False, 'incoerente: si con cronologia incompatibile', det
        return True, '', det


# ── prepara (Mac) ────────────────────────────────────────────────────────────────────────────────────────────────

def conta(testo, tok):
    return len(tok.encode(testo).ids) if tok else len(testo) // 3


def richiesta(dom, c, tok=None, priorita=0):
    ok, quota = freni.leggibile(c['q'])
    doc, _ = L14.doc_e_pagina(c['pid'], dom.prove)
    testo = dom.testo(c)
    tagliata = False
    if tok is not None and conta(testo, tok) > FINESTRA_MAX_TOKEN:
        # si taglia la FINESTRA, mai il fascicolo (regola del PI, 10/10)
        q = c['q']
        while q and conta(dom.testo(c, finestra=q), tok) > FINESTRA_MAX_TOKEN:
            q = q[: int(len(q) * 0.8)]
        testo, tagliata = dom.testo(c, finestra=q), True
    return {'id': c['id'], 'chiave': c['id'], 'gruppo': hashlib.md5(c['id'].encode('utf-8')).hexdigest()[:8],
            'priorita': priorita, 'testo': testo, 'letture': LETTURE_DS, 'tetto': TETTO_DS, 'puro': c['q'],
            'leggibile': ok, 'quota_parole': quota, 'caso': c['caso'], 'atto': doc, 'voce': c['voce'], 'lettore': 'ds',
            'codice': CODICE, 'finestra_tagliata': tagliata}


def scrivi(rr, uscita):
    n = collections.Counter()
    with gzip.open(uscita, 'wt', encoding='utf-8') as h:
        for r in rr:
            if not r['leggibile']:
                n['illeggibile'] += 1
                continue
            n['richieste'] += 1
            n['finestra_tagliata'] += r['finestra_tagliata']
            h.write(json.dumps(r, ensure_ascii=False) + '\n')
    return dict(n)


def comando_prepara(a):
    tok = None
    if a.tokenizer:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(a.tokenizer)
    s9 = QUI / 'training' / 'ponte_impl' / 's09'
    R = s9 / 'richieste'
    dati = L14.Dati()
    dom = DomandaL15(L14.Voci(), L14.Atti(), dati.prove())
    # le STESSE coppie di L14: gli id delle richieste DeepSeek di L14 (taratura e pool)
    ids_t = [r['id'] for r in L14.jl(R / 'ponte_impl_l14_ds_taratura.jsonl.gz')]
    ids_p = {r['id'] for r in L14.jl(R / 'ponte_impl_l14_ds_pool_tutte.jsonl.gz')}
    tutte = {c['id']: c for c in dati.coppie_prova()}
    pool = {c['id']: c for c in dati.pool()}
    taratura = [tutte[i] for i in ids_t]
    esempi_ids = [e['id'] for e in json.load(open(s9 / 'esempi' / 'esempi.json', encoding='utf-8'))]
    esempi = [pool[i] for i in esempi_ids if i in pool]
    # prova: tre coppie della taratura, una per tipo (la prima in ordine di id), lette UNA volta, fuori dalla misura
    T = json.load(open(s9 / 'taratura.json', encoding='utf-8'))
    prova = [next(c for c in sorted(taratura, key=lambda c: c['id']) if T[c['id']]['tipo'] == tipo) for tipo in ('test', 'negativo', 'noto')]
    conti = {}
    rp = [dict(richiesta(dom, c, tok), letture=1) for c in prova]
    conti['prova'] = scrivi(rp, R / 'ponte_impl_l15_ds_prova.jsonl.gz')
    conti['taratura'] = scrivi([richiesta(dom, c, tok) for c in taratura], R / 'ponte_impl_l15_ds_taratura.jsonl.gz')
    conti['esempi'] = scrivi([richiesta(dom, c, tok, 1) for c in esempi], R / 'ponte_impl_l15_ds_esempi.jsonl.gz')
    if not a.senza_pool:
        conti['pool'] = scrivi([richiesta(dom, pool[i], tok, 2) for i in sorted(ids_p) if i in pool],
                               R / 'ponte_impl_l15_ds_pool_tutte.jsonl.gz')
    print(json.dumps(conti, ensure_ascii=False, indent=1))


def raccogli(richieste, esiti):
    per = collections.defaultdict(list)
    for x in L14.jl(esiti):
        per[x['id']].append(x)
    out = {}
    for r in richieste:
        fr = FreniL15(r['puro'], DomandaL15.testi_prompt() + [r['testo']])
        voti, motivi, lett = collections.Counter(), collections.Counter(), []
        for x in sorted(per.get(r['id'], []), key=lambda y: y['lettura']):
            j = L13.esito_json(x.get('testo'))
            ok, motivo, det = fr.verifica(j)
            if isinstance(j, dict) and 'frase_finestra' in j:
                j = {**j, 'frase': j.get('frase_finestra')}       # per decidi_s09.Lettore.frase
            lett.append({'lettura': x['lettura'], 'valida': ok, 'motivo_scarto': motivo, 'verifica_frasi': det, 'json': j})
            if ok:
                voti[j['esito']] += 1
            else:
                motivi[motivo] += 1
        out[r['id']] = {'voti': dict(voti), 'valide': sum(voti.values()), 'scartate': dict(motivi), 'fatte': len(lett),
                        'previste': r.get('letture'), 'letture': lett}
    return out


def prova_freni():
    finestra = ('Each state must do its part: a country cannot escape its own responsibility by pointing out that its '
                'emissions are only a small share of the global total, because every reduction counts.')
    paragrafo = 'No reduction is negligible: partial responsibility of every country for its own share of the emissions.'
    fasc = 'Falso amico: la scienza IPCC sul bilancio di carbonio non e\' una ripresa di questa decisione.'
    fr = FreniL15(finestra, DomandaL15.testi_prompt() + [paragrafo + ' ' + fasc])
    buona = {'proposizione_specifica': 'x', 'distintiva': 'si', 'frase_finestra': 'a country cannot escape its own responsibility '
             'by pointing out that its emissions are only a small share of the global total', 'fonte_alternativa': '',
             'cronologia': 'compatibile', 'esito': 'si', 'motivo': 'stessa proposizione'}
    casi = [('lettura buona', buona, True),
            ('fonte alternativa «nessuna»', {**buona, 'fonte_alternativa': 'nessuna'}, True),
            ('frase copiata dal paragrafo', {**buona, 'frase_finestra': paragrafo}, False),
            ('frase copiata dal fascicolo', {**buona, 'frase_finestra': fasc}, False),
            ('frase inventata', {**buona, 'frase_finestra': buona['frase_finestra'] + ' and the court awarded ten million'}, False),
            ('si senza frase', {**buona, 'frase_finestra': ''}, False),
            ('si su luogo comune', {**buona, 'distintiva': 'no'}, False),
            ('si con fonte alternativa', {**buona, 'fonte_alternativa': 'IPCC AR6'}, False),
            ('si con cronologia incompatibile', {**buona, 'cronologia': 'incompatibile'}, False),
            ('no su luogo comune', {**buona, 'distintiva': 'no', 'esito': 'no', 'frase_finestra': ''}, True),
            ('esito fuori elenco', {**buona, 'esito': 'probabile'}, False)]
    return [(n, fr.verifica(j)[1]) for n, j, deve in casi if fr.verifica(j)[0] != deve]


def leggi(a):
    L13.CODICE = CODICE
    L13.leggi(a)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='fase', required=True)
    p = sp.add_parser('prepara'); p.add_argument('--tokenizer', default=''); p.add_argument('--senza-pool', action='store_true')
    p = sp.add_parser('secco'); p.add_argument('--richieste', required=True); p.add_argument('--tokenizer', default='')
    p.add_argument('--stampa', type=int, default=0)
    sp.add_parser('prova-freni')
    lg = sp.add_parser('leggi')
    lg.add_argument('--richieste', required=True); lg.add_argument('--uscita', required=True)
    lg.add_argument('--base-url', required=True); lg.add_argument('--chiave-file', required=True)
    lg.add_argument('--modello', required=True); lg.add_argument('--ragionamento', default='deepseek-high', choices=sorted(L13.CORPI))
    lg.add_argument('--contesto', type=int, default=L13.CONTESTO); lg.add_argument('--paralleli', type=int, default=16)
    lg.add_argument('--minuti', type=float, default=0); lg.add_argument('--tokenizer', default='')
    p = sp.add_parser('raccogli'); p.add_argument('--richieste', required=True); p.add_argument('--esiti', required=True)
    p.add_argument('--uscita', required=True)
    a = ap.parse_args()
    if a.fase == 'prepara':
        comando_prepara(a)
    elif a.fase == 'secco':
        print(json.dumps(L13.secco(L14.jl(a.richieste), a.tokenizer, a.stampa), ensure_ascii=False))
    elif a.fase == 'prova-freni':
        sb = prova_freni()
        print('PROVA DEI FRENI:', 'PASSA' if not sb else f'FALLISCE {sb}')
        sys.exit(1 if sb else 0)
    elif a.fase == 'leggi':
        leggi(a)
    else:
        ris = raccogli(L14.jl(a.richieste), a.esiti)
        json.dump(ris, open(a.uscita, 'w', encoding='utf-8'), ensure_ascii=False)
        print(len(ris), 'coppie ->', a.uscita)


if __name__ == '__main__':
    main()
