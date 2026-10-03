"""DEEPSEEK, TERZO GIRO: la scheda di oggi, la domanda corretta, il fascicolo.

   TRE MODI DI SPIEGARE URGENDA AL LETTORE, sulle stesse righe:
     v1  la scheda di cinque righe e la domanda a catena (§57.5, primo giro §61.5);
     v2  la stessa con tre avvertenze: due binari, il nome non serve, nel dubbio
         si propone (`ISTRUZIONI_CATENA_V2`, §61.6);
     v3  il FASCICOLO (`cited-cases/urgenda-fascicolo.md`, 23/09/2026, v1):
         le tre pronunce paragrafo per paragrafo e le fonti concorrenti, piu'
         il MODULO DI OSSERVAZIONI (domande chiuse, sotto).

   CINQUE LETTURE PER RIGA, indipendenti (temperatura 0,6): il numero di
   letture che dicono RIPRESA e' un punteggio con soglia sceglibile e AUC.

   PROVA E ADDESTRAMENTO. Gli errori letti per scrivere v2 erano sulle righe
   di prova; il fascicolo e' scritto senza nessun giudizio. Le tre versioni si
   misurano sulle 137 righe di prova E sulle 263 di addestramento: queste
   ultime servono anche ad addestrare il decisore sulle osservazioni.

   IL LETTORE NON VEDE I GIUDIZI. Riceve solo il testo; le etichette si usano
   dopo, per contare. Per questo la revisione delle righe «citazione altrove»
   non blocca la prova: si ricontano gli esiti con le etichette rivedute.

   IL FASCICOLO STA IN TESTA AL PROMPT, identico per ogni riga: vLLM lo calcola
   una volta e lo riusa (prefix caching). Sul Mac vale lo stesso.
"""
import argparse, json, pathlib, sys, time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
_m_giudica_llm = __import__('023_giudica_llm')
costruisci = _m_giudica_llm.costruisci
estrai = _m_giudica_llm.estrai

FONTI = ['Urgenda', 'Neubauer', 'KlimaSeniorinnen', 'Shell', 'Leghari', 'Juliana', 'Sacchi', 'Grande-Synthe',
         'Greenpeace Nordic', 'Duarte Agostinho', 'OC-23/17', 'OC-32/25', 'ICJ 2025', 'ITLOS 2024',
         'giurisprudenza CEDU ambientale', 'Accordo di Parigi / UNFCCC', 'CBDR', 'ARSIWA art. 47', 'no-harm',
         'precauzione', 'IPCC / scienza', 'costituzione nazionale', 'diritto interno', 'altro caso', 'nessuna']

MODULO = """{fascicolo}

========== FINE DEL FASCICOLO ==========

PROPOSIZIONE CERCATA (uno degli anelli della catena di Urgenda):
{proposizione}

TESTO DA ESAMINARE — piu' pagine consecutive di un atto o di una decisione di un ALTRO caso. Leggile per
intero, note a pie' di pagina comprese: il ragionamento comincia prima del punto che interessa e si chiude
dopo, e le note dicono a chi il testo attribuisce cio' che afferma.
---
{passaggio}
---

Usa il fascicolo. Rispondi alle domande in quest'ordine, SOLO con un oggetto JSON.

1. "chi_parla": una fra "corte", "parte", "corte_riassume_parte", "interveniente_o_amicus", "non_determinabile".
2. "cita_urgenda": il testo (corpo o note di queste pagine) nomina o cita Urgenda? true/false.
3. "paragrafi_urgenda": numeri di paragrafo di Urgenda citati, se ci sono (es. ["5.7.5","5.7.7"]); lista vuota se nessuno.
4. "fonti": le fonti su cui il testo appoggia il punto che interessa, SCEGLIENDO dall'elenco: {fonti}.
5. "fonte_principale": una sola voce dello stesso elenco: quella da cui il testo prende davvero il punto.
6. "tramite": se il testo prende il punto da una fonte che a sua volta lo costruisce su Urgenda (fascicolo § 5.4), il nome di quella fonte; altrimenti "".
7. "anelli": quali anelli (a)-(e) il testo percorre. Lista di lettere.
8. "afferma": il testo afferma la proposizione cercata (non solo ne parla)? true/false.
9. "autonomo": true se il passaggio reggerebbe identico anche se Urgenda non fosse mai esistita.
10. "citazione": VERBATIM, il pezzo piu' breve che mostra il punto.
11. "esito": "RIPRESA", "ALTRA_FONTE" o "NON_AFFERMA". Nel dubbio fra RIPRESA e ALTRA_FONTE scegli RIPRESA: un giurista rileggera' ogni riga che segnali.
12. "motivo": una frase, massimo venticinque parole.

Niente fuori dal JSON."""


# CHE COSA CONTA COME RIPRESA — decisione del PI, 23/09/2026 sera. Letti gli
# errori della versione 3 sulla prova: 18 riprese perse, quasi tutte scartate
# da DeepSeek perche' «applicata a Shell, non allo Stato», «la corte riassume le
# tesi delle ricorrenti», «e' un amicus». Il gruppo le aveva contate come
# riprese; il lettore aveva preso le sonde alla lettera. Il PI ha deciso:
# si conta in tutti e tre i casi, e il terzo si segnala.
REGOLE_PI = """
CHE COSA CONTA COME RIPRESA PER QUESTA RICERCA (regole del gruppo, valgono sopra ogni altra indicazione):
- Conta anche se la stessa ragione di Urgenda e' applicata a un'IMPRESA PRIVATA (per esempio Shell) invece che
  allo Stato: la proposizione cercata dice «lo Stato», ma quello che si cerca e' la circolazione della ragione.
- Conta anche se a dirla e' una PARTE, un INTERVENIENTE o un AMICUS CURIAE, e non la corte: chi parla si
  registra in "chi_parla", non e' un motivo per escludere.
- Conta anche se la CORTE RIASSUME l'argomento di una parte che la riprende: in quel caso "chi_parla" e'
  "corte_riassume_parte", ed e' cosi' che la riga viene segnalata.
"""


def prompt_fascicolo(r, fascicolo, regole=False):
    if regole:
        return MODULO.replace('Usa il fascicolo.', REGOLE_PI + '\nUsa il fascicolo.').format(
            fascicolo=fascicolo, proposizione=r['sonda_testo'],
            passaggio=(r.get('finestra_larga') or r['finestra'])[:28000], fonti=', '.join(FONTI))
    return MODULO.format(fascicolo=fascicolo, proposizione=r['sonda_testo'],
                         passaggio=(r.get('finestra_larga') or r['finestra'])[:28000], fonti=', '.join(FONTI))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modello', required=True)
    ap.add_argument('--letture', type=int, default=5)
    ap.add_argument('--memoria', type=float, default=0.85)
    ap.add_argument('--versioni', default='3,2,1')
    ap.add_argument('--parti', default='prova,addestramento')
    a = ap.parse_args()
    sys.path.insert(0, str(pathlib.Path(a.modello)/'encoding'))
    from encoding_dsv4 import encode_messages
    from vllm import LLM, SamplingParams
    T = QUI/'training'
    fascicolo = (QUI/'cited-cases'/'urgenda-fascicolo.md').read_text(encoding='utf-8')
    t0 = time.time()
    llm = LLM(model=a.modello, max_model_len=65536, gpu_memory_utilization=a.memoria, trust_remote_code=True,
              enable_prefix_caching=True)
    print(f'caricato in {time.time()-t0:.0f}s', flush=True)
    sp = SamplingParams(n=a.letture, temperature=0.6, top_p=0.95, max_tokens=8000, seed=20260923)
    for parte in a.parti.split(','):
        righe = [json.loads(x) for x in open(T/f'urgenda_decisione_{parte}_corrette_larghe.jsonl', encoding='utf-8') if x.strip()]
        for v in [int(x) for x in a.versioni.split(',')]:
            t0 = time.time()
            testi = [prompt_fascicolo(r, fascicolo) if v == 3 else costruisci(r, v) for r in righe]
            pr = [encode_messages([{'role': 'user', 'content': t}], thinking_mode='thinking') for t in testi]
            out = llm.generate(pr, sp)
            fuori = []
            for r, o in zip(righe, out):
                letture = [estrai(c.text.rpartition('</think>')[2] if '</think>' in c.text else c.text) for c in o.outputs]
                fuori.append({'id': r['id'], 'etichetta': r['etichetta'], 'sonda_id': r.get('sonda_id'),
                              'case_id': r.get('case_id'), 'letture': letture,
                              'voti_ripresa': sum(g.get('esito') == 'RIPRESA' for g in letture),
                              'token': [len(c.token_ids) for c in o.outputs]})
            (T/f'deepseek_g3_v{v}_{parte}.json').write_text(json.dumps(fuori, ensure_ascii=False, indent=1), encoding='utf-8')
            y = [x['etichetta'] for x in fuori]
            for soglia in (1, 2, 3, 5):
                p = [x['voti_ripresa'] >= soglia for x in fuori]
                tp = sum(u and q for u, q in zip(y, p)); P = sum(p)
                print(f'  v{v} {parte:13s} almeno {soglia}/{a.letture}: propone {P:3d}  precisione {tp/max(P,1):.0%}  trova {tp}/{sum(y)} = {tp/max(sum(y),1):.0%}', flush=True)
            n_tok = sum(sum(x['token']) for x in fuori)
            print(f'v{v} {parte}: {len(righe)} righe in {time.time()-t0:.0f}s, {n_tok/len(righe)/a.letture:.0f} token a lettura', flush=True)


if __name__ == '__main__':
    main()
