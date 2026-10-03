"""The instructions given to DeepSeek by the three readers, verbatim from the live scripts.

- :data:`MODULO_TIPO`: the citation-type reading (L02 Urgenda, L03 the other cases), ``tools/classifica_lessicali.py``;
- :data:`MODULO_PAGINE_ATTORNO`: the uptake reading with the surrounding pages (L05), ``tools/leggi_ripresa.py``;
- :func:`istruzioni_l04`: the principles reading as it was on 27/09/2026 (L04), ``tools/leggi_l04.py``: today's L05
  instructions without the three additions of 28/09 (the dossier, the footnote rule with evidence copied word for word,
  question 3 on the supported sentence).

The texts are copied character for character (``tests/test_lettori.py`` checks them against the live modules and the
prompts recorded by the harness). The long lines are part of the prompts: they are not wrapped.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

MODULO_TIPO = """Sei un giurista che codifica citazioni giurisprudenziali per una ricerca sul contenzioso climatico.
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

MODULO_PAGINE_ATTORNO = """Sei un giurista che codifica le riprese di una sentenza climatica in atti successivi.
Il caso citato e' {nome_caso}.
{fascicolo}
I PRINCIPI DEL CASO (id, titolo, testo di riferimento):
{principi}

DOCUMENTO: {case_name} ({tipo_atto}, {data}), documento {document_id}.
La rete lessicale ha trovato il nome «{forma}» nel punto marcato con ⟦ ⟧, dentro il brano racchiuso fra
[[INIZIO DEL BRANO SEGNALATO]] e [[FINE DEL BRANO SEGNALATO]]. Ecco la pagina della citazione con la fine della
precedente e l'inizio della successiva:
---
{contesto}
---
{aiuto_paragrafi}
PAGINE VICINE DELLO STESSO ATTO (possibile seguito della ripresa, senza il nome del caso):
{vicine}

DOMANDA 1. Quali principi del caso questa citazione prende, cioe' usa, applica, discute o respinge? Anche piu'
d'uno. "nessuno" se la citazione non prende nessun principio (elenco di precedenti, solo descrizione dei fatti o
dell'esito, esempio di contenzioso). "altro" se prende qualcosa che non e' nella lista: scrivilo in una frase.

DOMANDA 2. Per ogni pagina vicina: prosegue LA STESSA RIPRESA? Si', solo se sviluppa uno dei principi presi
dalla citazione dentro lo stesso ragionamento avviato dalla citazione. No, se parla d'altro, oppure se regge lo
stesso tema su un'altra fonte (CEDU generale, Accordo di Parigi, un altro caso) senza legame con la citazione.
GUARDA LE NOTE: se la frase della pagina vicina ha una sua nota che la attribuisce a un'altra fonte, non prosegue.
Se la citazione non prende nessun principio (elenco, sola descrizione), nessuna pagina prosegue.

DOMANDA 3. Quale FRASE DELL'ATTO sostiene la citazione? E' la frase del testo a cui e' agganciata la nota che cita il
caso, oppure la frase che contiene la citazione. Copiala ALLA LETTERA, nella sua lingua, massimo 60 parole. Il principio
si decide su questa frase, non sull'argomento della pagina.

Rispondi SOLO con un oggetto JSON:
{{"frase_sostenuta": "frase copiata alla lettera", "principi": [id...], "altro": "", "motivo": "una frase, massimo trenta parole",
  "vicine": [{{"pagina": numero, "prosegue": true o false, "principio": "id o vuoto", "prova": "frase COPIATA ALLA LETTERA dalla pagina, nella sua lingua, massimo 25 parole; mai un tuo riassunto"}}]}}
Niente fuori dal JSON."""

_DOMANDA_3 = """DOMANDA 3. Quale FRASE DELL'ATTO sostiene la citazione? E' la frase del testo a cui e' agganciata la nota che cita il
caso, oppure la frase che contiene la citazione. Copiala ALLA LETTERA, nella sua lingua, massimo 60 parole. Il principio
si decide su questa frase, non sull'argomento della pagina.

"""

_NOTE = """
GUARDA LE NOTE: se la frase della pagina vicina ha una sua nota che la attribuisce a un'altra fonte, non prosegue.
Se la citazione non prende nessun principio (elenco, sola descrizione), nessuna pagina prosegue."""

NOMI_BREVI: Mapping[str, str] = {
    'urgenda': 'Urgenda',
    'neubauer': 'Neubauer',
    'future-generations': 'Future Generations',
}
"""Short names of the cases in the type prompt (tools/classifica_lessicali.py NOMI_BREVI)."""
INIZIO, FINE = '[[INIZIO DEL BRANO SEGNALATO]]', '[[FINE DEL BRANO SEGNALATO]]'
"""Marks around the flagged passage in the row context."""


def modulo_tipo(caso: str, conf: Mapping[str, Any] | None = None) -> str:
    """The type instructions of ``caso`` (tools/classifica_lessicali.py ``modulo``).

    For Urgenda the text of always (the readings of 26-27/09 stay comparable). For the other cases the Urgenda lines
    become generic and the "homonym" is the person or party who bears the name.

    Args:
        caso: the cited case.
        conf: the base case file (``cited-cases/<caso>.yaml``), for name and decision date.
    """
    if caso == 'urgenda':
        return MODULO_TIPO
    conf = conf or {}
    breve = NOMI_BREVI.get(caso, caso)
    m = MODULO_TIPO.replace(
        "Il caso citato e' URGENDA: Stichting Urgenda c. Stato dei Paesi Bassi (Rechtbank Den Haag 24/6/2015,\n"
        'Gerechtshof Den Haag 9/10/2018, Hoge Raad 20/12/2019). Chi cita uno qualunque dei tre gradi cita Urgenda.',
        f"Il caso citato e' {conf.get('nome')} (decisione del {conf.get('data_decisione')}).",
    )
    m = m.replace(
        '"caso_urgenda" (il caso o una delle sue\n   pronunce), "fondazione_urgenda" (la fondazione come soggetto, non la sentenza: per esempio parte in un\n   altro giudizio)',
        '"caso" (il caso o una delle sue\n   pronunce), "soggetto_omonimo" (la persona, la parte o l\'organizzazione che porta il nome, non la sentenza: per esempio\n   un\'attivista o una parte in un altro giudizio)',
    )
    return (
        m.replace('"caso_urgenda"', '"caso"').replace('paragrafi_urgenda', 'paragrafi_caso').replace('Urgenda', breve)
    )


def blocchi_codebook(cb: Mapping[str, Any]) -> tuple[str, str, str]:
    """The three codebook blocks of the type prompt: types, who speaks, borderline cases (tools ``codebook``)."""
    tipi = '\n'.join(
        f'- "{t["codice"]}" ({t["nome"]}): {" ".join(t["definizione"].split())} Indizi: {"; ".join(t.get("indizi") or [])}.'
        for t in cb['tipo_citazione']
    )
    chi = '\n'.join(f'- "{c["codice"]}": {c["nome"]}' for c in cb['chi_parla'])
    limiti = '\n'.join(
        f'- {" ".join(c["questione"].split())} Regola: {" ".join(str(c["regola"]).split())}' for c in cb['casi_limite']
    )
    return tipi, chi, limiti


def istruzioni_l04(modulo: str = MODULO_PAGINE_ATTORNO) -> str:
    """The L04 instructions out of the L05 ones (tools/leggi_l04.py ``istruzioni_l04``).

    Raises:
        AssertionError: one of the removed pieces is not in ``modulo`` exactly once (as live).
    """
    m = modulo
    for vecchio, nuovo in [
        ('\n{fascicolo}', ''),
        (_NOTE, ''),
        (_DOMANDA_3, ''),
        ('{{"frase_sostenuta": "frase copiata alla lettera", "principi"', '{{"principi"'),
        (
            '"prova": "frase COPIATA ALLA LETTERA dalla pagina, nella sua lingua, massimo 25 parole; mai un tuo riassunto"',
            '"prova": "frase testuale della pagina, massimo 25 parole"',
        ),
    ]:
        assert m.count(vecchio) == 1, vecchio[:40]
        m = m.replace(vecchio, nuovo)
    return m


MODULO_PRINCIPI = istruzioni_l04()
"""The L04 instructions."""


def kwargs_modello(testo: str, sforzo: str) -> dict[str, Any]:
    """The ``extra_body`` of the type reading: ``--kwargs-modello`` JSON if given, else thinking with ``sforzo``."""
    return (
        {'chat_template_kwargs': json.loads(testo)}
        if testo
        else {'chat_template_kwargs': {'thinking': True, 'reasoning_effort': sforzo}}
    )
