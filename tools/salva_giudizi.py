"""COPIA DI SICUREZZA DEL LAVORO UMANO.

   Non del corpus: quello si rigenera dai PDF, e l'indice si ricostruisce con
   sei ore di GPU noleggiata. I giudizi no. Sono l'unica cosa in tutta la
   catena che, se sparisce, non si rifa' — perche' rifarla vuol dire chiedere a
   quattro persone di rileggere tremila passaggi.

   Salva ogni riga che ha un `esito`, con TUTTI i suoi campi e la sua
   sottocollezione `storia`, cioe' il registro di chi ha cambiato cosa e
   quando. Sola lettura: non scrive niente su Firestore.

   Si lancia cosi', e conviene farlo a fine giornata di validazione:
       .venv/bin/python3 tools/salva_giudizi.py
   Scrive `giudizi-umani-AAAA-MM-GG.json` nella radice del corpus. Un file per
   giorno, quindi rilanciarlo lo stesso giorno sovrascrive quello di oggi e
   lascia intatti quelli dei giorni prima.
"""
import datetime
import json
import pathlib

from google.cloud import firestore

# Il nome del progetto sta in `pubblica.py`, ma importarlo trascinerebbe dentro
# tutto quel programma solo per una stringa — e da una cartella diversa non lo
# trova nemmeno. Si dichiara qui: se un giorno cambia, cambia in due posti, ed
# e' meno fragile di un'importazione che dipende da dove sei quando lanci.
PROGETTO = 'climpact-drp'
QUI = pathlib.Path(__file__).resolve().parent.parent

db = firestore.Client(project=PROGETTO)
fuori = []
for d in db.collection('corpus_rows').stream():
    x = d.to_dict()
    if not x.get('esito'): continue
    x['_id'] = d.id
    # anche la storia delle modifiche, che e' il registro di chi ha cambiato cosa
    x['_storia'] = [s.to_dict() for s in d.reference.collection('storia').stream()]
    fuori.append(x)
oggi = datetime.date.today().isoformat()
p = QUI/f'giudizi-umani-{oggi}.json'
p.write_text(json.dumps(fuori, indent=1, default=str), encoding='utf-8')
print(f'salvati {len(fuori)} giudizi in {p}')
print(f'dimensione: {p.stat().st_size/1024:.0f} KB')
