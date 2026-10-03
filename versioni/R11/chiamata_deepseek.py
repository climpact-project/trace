"""UNA CHIAMATA A DEEPSEEK CHE NON SI PERDE IN SILENZIO (02/10/2026).

   Fino a oggi ogni lettore aveva la sua funzione `chiama`: cinque tentativi sugli errori di rete, e se la risposta
   arrivava vuota la si salvava vuota, senza dire perche'. Misura del 02/10: nei log di vLLM 32.000 richieste tutte
   andate a buon fine (200) e nessun rifiuto per contesto; eppure fra il 10 e il 29% delle letture L05, fino al 10%
   delle L04 e l'1-4% di quelle del tipo erano vuote, con il ragionamento presente e la risposta mancante. DeepSeek
   esauriva il tetto della risposta (8.000 token) ragionando, prima di scrivere. Le righe vuote non sono quasi piu'
   lunghe delle altre (mediana 20.000 caratteri contro 18.500 su Neubauer): il ragionamento lungo capita quasi a caso.

   Qui, deciso col PI:
     1. fino a tre tentativi IDENTICI (stesse istruzioni, stesso tetto): la stessa domanda, ripetuta, di solito riesce;
     2. se dopo i tre tentativi la risposta e' ancora troncata (`finish_reason` = 'length'), un ultimo tentativo col
        tetto alzato fino a 16.000 token, ma mai oltre lo spazio che resta nel contesto di vLLM (65.536 token meno la
        domanda): variante dichiarata nel registro;
     3. ogni lettura porta con se' come e' andata: tentativi, motivo di fine, tetto usato, errore se ce n'e' stato;
     4. (02/10/2026 sera) una risposta vuota chiusa normalmente si recupera dal JSON con cui finisce il ragionamento
        (`json_finale`), segnata `dal_ragionamento`: vale come un tentativo (misura in GIRI-E-DOMANDA.md).

   Uso dentro i lettori:  ris = chiama(cli, modello, testo, extra_body)
                          ris['testo'], ris['ragionamento'], ris['token'], ris['chiamata']
"""
import hashlib, time

TETTO = 8000            # il tetto delle letture L03, L04, L05 di settembre
TETTO_ALTO = 16000      # solo per l'ultimo tentativo, dopo tre risposte troncate
CONTESTO = 65536        # --max-model-len di vLLM (chat/vllm2.sh)
MARGINE = 512


def _ragionamento(m):
    return (getattr(m, 'reasoning_content', None) or getattr(m, 'reasoning', None)
            or (getattr(m, 'model_extra', None) or {}).get('reasoning') or '')


def json_finale(ragionamento):
    """IL JSON ALLA FINE DEL RAGIONAMENTO (02/10/2026, il PI: «devi farlo sempre, deve entrare in pipeline»). Misura del
    02/10 (training/misure/GIRI-E-DOMANDA.md): il 6,3% dei tentativi L05 torna con la risposta vuota e fine «stop»; nel
    97,4% di questi il ragionamento FINISCE con un JSON completo e valido, che prende la stessa decisione di un nuovo
    tentativo quanto due tentativi riusciti fra loro (61,8% contro 60,3%). Vale quindi come un tentativo: si prende solo
    se e' l'ultima cosa scritta (dopo, solo spazi o recinti ```), mai una bozza a meta' ragionamento."""
    import json
    t = (ragionamento or '').rstrip()
    while t.endswith('```'):
        t = t[:-3].rstrip()
    if not t.endswith('}'):
        return ''
    dec = json.JSONDecoder()
    i = t.rfind('{')
    while i >= 0:
        try:
            obj, fine = dec.raw_decode(t, i)
            if fine == len(t) and isinstance(obj, dict):
                return t[i:fine]
        except ValueError:
            pass
        i = t.rfind('{', 0, i)
    return ''


def chiama(cli, modello, testo, extra_body, tetto=TETTO, tentativi=3, errori_rete=5, temperatura=None, seme=None):
    # temperatura e seme (02/10/2026): se non dati, come prima (i valori del modello); se dati, passano al server.
    # Ogni chiamata registra l'impronta delle istruzioni e tutti i parametri, per poterla rifare identica.
    campi = {}
    if temperatura is not None:
        campi['temperature'] = temperatura
    if seme is not None:
        campi['seed'] = seme
    storia, prompt_token, ultimo = [], None, None
    piano = [tetto] * tentativi
    k = 0
    while k < len(piano):
        cap = piano[k]
        for prova in range(errori_rete):
            try:
                r = cli.chat.completions.create(model=modello, messages=[{'role': 'user', 'content': testo}],
                                                max_tokens=cap, extra_body=extra_body, **campi)
                break
            except Exception as e:              # rete o server: si ritenta, e l'errore resta scritto
                storia.append({'tetto': cap, 'errore': repr(e)[:300]})
                time.sleep(5 * (prova + 1))
        else:
            k += 1
            continue
        c = r.choices[0]; m = c.message
        prompt_token = getattr(r.usage, 'prompt_tokens', None) or prompt_token
        ultimo = {'testo': m.content or '', 'ragionamento': _ragionamento(m),
                  'token': getattr(r.usage, 'completion_tokens', 0), 'fine': c.finish_reason, 'tetto': cap}
        storia.append({'tetto': cap, 'fine': c.finish_reason, 'token': ultimo['token']})
        # risposta vuota ma chiusa normalmente: se il ragionamento finisce con un JSON valido, quello e' la risposta
        if not ultimo['testo'].strip() and c.finish_reason == 'stop':
            dal = json_finale(ultimo['ragionamento'])
            if dal:
                ultimo['testo'] = dal; ultimo['dal_ragionamento'] = True; storia[-1]['dal_ragionamento'] = True
        if ultimo['testo'].strip():
            break
        k += 1
        # dopo i tentativi identici, se e' troncata: uno solo col tetto alto, nello spazio che resta nel contesto
        if k == tentativi and c.finish_reason == 'length' and prompt_token:
            alto = min(TETTO_ALTO, CONTESTO - prompt_token - MARGINE)
            if alto > cap:
                piano.append(alto)
    esito = ultimo or {'testo': '', 'ragionamento': '', 'token': 0, 'fine': None, 'tetto': tetto}
    esito['chiamata'] = {'tentativi': len(storia), 'fine': esito.get('fine'), 'tetto': esito.get('tetto'),
                         'prompt_token': prompt_token, 'riuscita': bool(esito['testo'].strip()),
                         'dal_ragionamento': bool(esito.get('dal_ragionamento')),
                         'storia': storia, 'modello': modello,
                         'istruzioni_sha256': hashlib.sha256(testo.encode('utf-8')).hexdigest(),
                         'parametri': {'max_tokens': tetto, 'temperature': temperatura, 'seed': seme, 'extra_body': extra_body}}
    try:                    # nel giornale delle operazioni, se lo strumento l'ha avviato
        import giornale
        giornale.chiamata_deepseek(esito['chiamata'])
    except Exception:
        pass
    return esito


def vuota(lettura):
    """una lettura salvata senza risposta (il segno lasciato da estrai_tollerante su un testo vuoto)"""
    return isinstance(lettura, dict) and 'grezzo' in lettura and not str(lettura.get('grezzo') or '').strip()


def valida(y):
    """una lettura che e' una risposta: letta (non vuota) e non illeggibile"""
    return isinstance(y, dict) and not vuota(y) and y.get('esito') != 'ILLEGGIBILE'


def tenute(prima, domanda):
    """(indici delle letture valide di `prima` fatte con questa stessa domanda, quante valide sono state fatte con
    un'altra). La domanda si riconosce dall'impronta SHA-256 che chiamata_deepseek scrive in ogni lettura dal 02/10/2026;
    una lettura senza impronta non si puo' verificare e non si tiene."""
    import hashlib
    if not prima:
        return [], 0
    h = hashlib.sha256(domanda.encode('utf-8')).hexdigest()
    letture, chiamate = prima.get('letture') or [], prima.get('chiamate') or []
    ok, altre = [], 0
    for k, y in enumerate(letture):
        if not valida(y):
            continue
        c = chiamate[k] if k < len(chiamate) else None
        if isinstance(c, dict) and c.get('istruzioni_sha256') == h:
            ok.append(k)
        else:
            altre += 1
    return ok, altre
