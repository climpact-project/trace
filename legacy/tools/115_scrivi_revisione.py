"""SCRIVE SULLA PIATTAFORMA LA REVISIONE DELLE 20 RIGHE «CITAZIONE ALTROVE» (26/09/2026).

   Decisioni in `riclassificate-rivedute-2026-09-23.json` (tools/113_rivedi_altrove.py). Per ogni riga:
   - campo `revisione` = {esito, nota, data, da}; `da` e' il PI, che ha deciso (in alcune righe su
     proposta, scritto nella nota);
   - l'esito si aggiorna come farebbe il portale: «si» -> confermata sulla sua sonda; «altra:X» ->
     riclassificata sulla sonda X; «no» -> resta scartata (motivo citazione_altrove); «da_discutere» ->
     l'esito resta, e `da_discutere: true` la segnala alla revisione collettiva;
   - una voce nella sottocollezione `storia` con cio' che c'era prima (come `annota` del portale);
   - `validato_da` NON si tocca: chi aveva giudicato resta registrato.
   Uso:  python3 tools/115_scrivi_revisione.py         (prova: mostra cosa scriverebbe)
         python3 tools/115_scrivi_revisione.py --scrivi
"""
import json, pathlib, sys
from google.cloud import firestore
QUI = pathlib.Path(__file__).resolve().parent.parent
PI = 'TKuaPxLsEobzv43Bdj7jrzyaVjs2'
SONDE = {'target_giudiziale': "Il giudice puo' fissare il minimo quantificato ricavandolo dal consenso scientifico e internazionale"}
scrivi = '--scrivi' in sys.argv
db = firestore.Client(project='climpact-drp')
dec = json.loads((QUI/'riclassificate-rivedute-2026-09-23.json').read_text(encoding='utf-8'))
for rid, d in sorted(dec.items(), key=lambda kv: kv[1]['n']):
    ref = db.collection('corpus_rows').document(rid); r = ref.get().to_dict()
    esito = d['esito_pi']; campi = {}
    if esito == 'si':
        campi = {'esito': 'confermata', 'motivo_scarto': None, 'validato_sonde': [r['sonda']]}
    elif esito.startswith('altra:'):
        campi = {'esito': 'riclassificata', 'motivo_scarto': None, 'validato_sonde': [SONDE[esito.split(':', 1)[1]]]}
    elif esito == 'da_discutere':
        campi = {'da_discutere': True}
    rev = {'esito': esito, 'nota': d['nota_pi'], 'data': firestore.SERVER_TIMESTAMP, 'da': PI}
    if esito.startswith('altra:'):
        rev['posizione'] = 'critica'
    prima = {k: r.get(k) for k in ('esito', 'motivo_scarto', 'validato_sonde', 'da_discutere')}
    print(f"riga {d['n']:2d} {rid[:70]:70s} {prima['esito']} -> {campi.get('esito', prima['esito'])}"
          + ('  [da discutere]' if campi.get('da_discutere') else ''))
    if scrivi:
        ref.update({**campi, 'revisione': rev})
        ref.collection('storia').add({'azione': 'revisione', 'campi': {**campi, 'revisione': {**rev, 'data': None}},
                                      'prima': prima, 'chi': PI, 'quando': firestore.SERVER_TIMESTAMP})
print('SCRITTO' if scrivi else 'PROVA: niente scritto')
