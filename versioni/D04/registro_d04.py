# ruff: noqa: E501  (la voce si inserisce in registro_versioni.py e ne tiene lo stile: righe lunghe come le altre voci)
"""LA VOCE D04 NEL REGISTRO DELLE VERSIONI (03/10/2026): la patch preparata con D04, rifatta e applicata dal ciclo.

   La patch del 03/10 notte (`tools/registro_versioni_D04.patch`) non si applica piu': fra la voce S05 e la voce T01 di
   `tools/registro_versioni.py` ora c'e' la voce S06, e il contesto della patch non torna. Qui la stessa voce, con lo
   stato aggiornato (in uso dal caricamento delle 13 righe) e le misure del ciclo D04, si inserisce cercando tre punti
   fissi del file (prima della voce T01, dopo D03 nei due elenchi CAMBIA e NOMI). Il file si riscrive accanto e si
   sposta al suo posto (mai modificato mentre qualcuno lo legge); se la voce c'e' gia' non si fa niente.

   Uso:  .venv/bin/python tools/registro_d04.py            dice cosa farebbe
         .venv/bin/python tools/registro_d04.py --scrivi   scrive tools/registro_versioni.py
"""
import argparse
import os
import pathlib
import sys

QUI = pathlib.Path(__file__).resolve().parent.parent
FILE = QUI/'tools'/'registro_versioni.py'

PRIMA_DI_T01 = "    R.append({'codice': 'T01', 'tipo': 'modello', 'nome': 'TRACE-Reranker 0.1',\n"
DOPO_CAMBIA_D03 = "        'D03': ('D02', \"il Markdown di 277 atti dell'aggiornamento del 19/09/2026 che avevano solo il testo\"),\n"
DOPO_NOMI_D03 = "        'D03': ('Documents: D02 with Markdown for 277 filings of the 19/09/2026 update', 'in uso'),\n"

VOCE = '''    # D04 (03/10/2026): i 27 atti del 19/09 mai scaricati e i 20 file non PDF mai estratti
    # (training/misure/CORPUS-DIFETTI-2026-10-03.md). Voce inserita da tools/registro_d04.py nel ciclo D04
    # (tools/ciclo_d04.sh), dopo il calcolo di T01; conti e prove in training/d04/.
    f4 = QUI/'training'/'d04'/'conti.json'
    if f4.exists():
        c4 = json.load(open(f4, encoding='utf-8'))
        misure4 = [{'nome': 'atti nuovi nel corpus', 'valore': ("46 Markdown: 26 PDF riscaricati, 20 atti non PDF (16 .docx, 3 .doc, "
                                                                 "1 .png); 1.025 pagine aggiunte all'indice delle pagine")},
                   {'nome': 'righe nuove della ricerca per nome S05 sui documenti di D04',
                    'valore': f"{c4['righe']}: " + ', '.join(f'{k} {v}' for k, v in c4['casi'].items())}]
        fp4 = QUI/'training'/'d04'/'t01_prova_recas-ferma.json'
        if fp4.exists():
            p4 = json.load(open(fp4, encoding='utf-8'))
            misure4.append({'nome': 'punteggi T01 delle righe di D04 (recas-ferma): stesse coppie rifatte contro le H100 del ciclo S05',
                            'valore': (f"{p4['coppie']} coppie, differenza media {p4['differenza_media']}, massima {p4['differenza_massima']}, "
                                       f"cambi di lato alla soglia 0,5: {p4['cambi_di_lato']} ({p4['cambi_di_lato_lontani_dalla_soglia']} lontani dalla soglia)")})
        ff4 = QUI/'training'/'d04'/'pdf_d04.json'
        if ff4.exists():
            pdf4 = json.load(open(ff4, encoding='utf-8'))['pdf']
            misure4.append({'nome': 'PDF riscaricati sul server del corpus (corpus.climpact.it/pdf/), serviti con la lunghezza giusta',
                            'valore': f"{sum(1 for x in pdf4 if x.get('servito') == ['200', x['byte']])} su {len(pdf4)}"})
        R.append({'codice': 'D04', 'tipo': 'corpus', 'nome': "D03 con 27 atti dell'aggiornamento del 19/09 riscaricati e 20 atti non PDF estratti",
                  'compito': ("Come D03, piu' (1) 27 atti dell'aggiornamento del 19/09/2026 mai scaricati (fetch_sabin.py aveva trovato occupato il "
                              "nome troncato e scritto in manifest.jsonl, con http 0, l'impronta del file di luglio): riscaricati il 03/10 con un "
                              "nome nuovo, impronte vere in manifest_supplemento_2026-10-03.jsonl (manifest.jsonl non toccato); 26 file nuovi, 1 "
                              "identico alla fonte a un atto gia' nel corpus (Suncor amicus-brief-18 = amicus-brief-21, _b0d1) e non riscritto; "
                              "(2) 20 atti non PDF (16 .docx, 3 .doc, 1 .png) mai estratti, perche' extract_text.py legge solo i PDF. Testo come "
                              "il corpus (PyMuPDF, OCR Vision solo dove il testo e' inservibile, con freni.leggibile), Markdown con il front matter "
                              "di build_markdown.py, nomi nuovi in creazione esclusiva, nessun file esistente toccato; 1.025 pagine aggiunte "
                              "all'indice delle pagine (il vivo di prima resta in index/pagine/pagine.prima-D04.jsonl.gz). Le righe trovate "
                              "dalla ricerca per nome S05 sui soli documenti nuovi hanno provenienza.corpus D04 ed estrazione S05, e ricevono le "
                              "stesse letture delle altre: cinque del tipo e cinque L05 sulle pagine attorno R10, composte con R11, freni compresi."),
                  'data': '2026-10-03', 'stato': 'in uso dal caricamento del ciclo D04 (righe con provenienza.corpus D04)',
                  'fonte': 'Sabin Center for Climate Change Law, aggiornamento del 19/09/2026, scaricato di nuovo il 03/10/2026',
                  'versione': 'CCC-whole_data_dump-2026-09-19 (27 atti) e file non PDF di luglio',
                  'pesi': [{'file': 'manifest_supplemento_2026-10-03.jsonl', 'sha256': sha(QUI/'manifest_supplemento_2026-10-03.jsonl')},
                           {'file': 'training/difetti-2026-10-03/registro_non_pdf.json', 'sha256': sha(QUI/'training'/'difetti-2026-10-03'/'registro_non_pdf.json')},
                           {'file': 'training/d04/markdown_d04_registro.json', 'sha256': sha(QUI/'training'/'d04'/'markdown_d04_registro.json')},
                           {'file': 'index/pagine/pagine.d04.aggiunte.jsonl.gz', 'sha256': sha(QUI/'index'/'pagine'/'pagine.d04.aggiunte.jsonl.gz')}],
                  'codice_sorgente': copia('D04', 'tools/scarica_d04.py', 'tools/estrai_non_pdf.py', 'tools/build_markdown_d04.py', 'tools/cerca_d04.py',
                                           'tools/recupero_d04.py', 'tools/letture_d04.py', 'tools/registro_d04.py', 'tools/ciclo_d04.sh',
                                           'tools/launchd/attesa_d04.sh', 'tests/test_recupero_d04.py'),
                  'misure': misure4,
                  'note': ("Verifica dei 27 senza l'impronta del manifest (per loro e' quella sbagliata): tipo application/pdf, lunghezza uguale a "
                           "Content-Length, PyMuPDF apre il file, impronta diversa da quella del manifest e del file di luglio (e del .pdf.orig), "
                           "prima pagina letta: il caso e' giusto in tutti. Due file alla fonte non sono il tipo d'atto del titolo: Maules Creek "
                           "_925f ('judgment') e' la citazione introduttiva (summons), Pacific Coast _4954 ('order') e' un atto di Chevron. "
                           "Cinque atti non PDF escono a pagina unica (i 3 .doc e 2 .docx senza interruzioni segnate). Resta fuori il PDF di "
                           "Sebastiao (_67a5), troncato alla fonte. Le righe sugli atti non PDF non hanno un PDF da mostrare: il portale apre "
                           "la pagina della fonte.")})
'''
CAMBIA_D04 = ("        'D04': ('D03', \"27 atti dell'aggiornamento del 19/09 riscaricati (mai scaricati per un nome occupato) "
              "e 20 atti non PDF estratti\"),\n")
NOMI_D04 = ("        'D04': ('Documents: D03 with 27 filings of the 19/09/2026 update downloaded again and 20 non-PDF "
            "filings extracted', 'in uso'),\n")


def applica(testo):
    """il testo del registro con la voce D04; lo stesso testo se c'e' gia'. ValueError se un punto fisso manca."""
    if "'codice': 'D04'" in testo:
        return testo
    for nome, ancora in (('voce T01', PRIMA_DI_T01), ('CAMBIA D03', DOPO_CAMBIA_D03), ('NOMI D03', DOPO_NOMI_D03)):
        if testo.count(ancora) != 1:
            raise ValueError(f'punto fisso «{nome}» trovato {testo.count(ancora)} volte (atteso 1)')
    testo = testo.replace(PRIMA_DI_T01, VOCE + PRIMA_DI_T01)
    testo = testo.replace(DOPO_CAMBIA_D03, DOPO_CAMBIA_D03 + CAMBIA_D04)
    return testo.replace(DOPO_NOMI_D03, DOPO_NOMI_D03 + NOMI_D04)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scrivi', action='store_true')
    ap.add_argument('--file', default=str(FILE))
    a = ap.parse_args()
    f = pathlib.Path(a.file)
    prima = f.read_text(encoding='utf-8')
    dopo = applica(prima)
    if dopo == prima:
        print(f"la voce D04 c'e' gia' in {f.name}: niente da fare")
        return 0
    print(f'{f.name}: + voce D04 ({len(dopo.splitlines()) - len(prima.splitlines())} righe)')
    if not a.scrivi:
        print('ANTEPRIMA: niente scritto')
        return 0
    tmp = f.with_name(f.name + '.d04-tmp')
    tmp.write_text(dopo, encoding='utf-8')
    compile(dopo, str(f), 'exec')           # un errore di sintassi ferma qui, prima di toccare il file vero
    if f.read_text(encoding='utf-8') != prima:
        tmp.unlink()
        raise SystemExit(f'{f.name} e\' cambiato mentre lo si leggeva: rifare')
    os.replace(tmp, f)
    print('scritto', f)
    return 0


if __name__ == '__main__':
    sys.exit(main())
