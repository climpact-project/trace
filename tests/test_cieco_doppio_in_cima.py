"""L'ordine in cima delle righe dell'insieme in codifica doppia (05/10/2026): sta sotto ogni blocco, e' stabile, e il
posto in coda risultante e' quello atteso."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import cieco_doppio_coppie as c  # noqa: E402


def test_ordine_in_cima_sotto_i_blocchi_e_stabile():
    o = [c.ordine_in_cima(f'riga{i}') for i in range(200)]
    assert all(-10.0 <= x < -9.9 for x in o)         # i blocchi stanno fra -1 e -0,9
    assert o == [c.ordine_in_cima(f'riga{i}') for i in range(200)]
    assert len(set(o)) == 200


def test_posti_in_coda():
    righe = [(f'u{i}', {'caso_citato': 'urgenda', 'ordine': i / 10}) for i in range(5)]
    righe.append(('fatta', {'caso_citato': 'urgenda', 'ordine': 0.0, 'esito': 'si'}))
    nuovi = {'u3': c.ordine_in_cima('u3'), 'u4': c.ordine_in_cima('u4')}
    p = c.posti_in_coda(righe, nuovi)['urgenda']
    assert (p['in_coda'], p['posto_min'], p['posto_max']) == (5, 1, 2)
    assert c.posti_in_coda(righe, {}, {'u3', 'u4'})['urgenda']['posto_max'] == 5
