"""T01 PER LE RIGHE DI S06 (03/10/2026): I PUNTEGGI DEL TRACE-RERANKER SENZA FERMARE DEEPSEEK.

   Il problema. Sulle H100 di ReCaS i punteggi T01 si sono sempre calcolati fermando vLLM su una GPU del lavoro
   di DeepSeek (ciclo_s05.sh, punteggi_dentro.sh). Dal 03/10 la regola del PI e': vLLM non si ferma mai. Nelle GPU
   dei due lavori restano 3,2-4,5 GB liberi per scheda (nvidia-smi del 03/10 alle 9:10: 77-78 GB usati su 81,5),
   meno degli 8 GB dei pesi. Il Mac del gruppo (Apple M5 Pro, 24 GB) il 03/10 mattina era pieno (swap 26 GB su 28,
   un altro calcolo da 13 GB): il modello non si e' caricato in cinque minuti. Tre modi, scelti in
   training/s06/t01_modo.txt; la scelta del 03/10 e' recas-ferma:
     recas-ferma    lo schema del 01/10 (coda-ds2/fatti/punteggi_dentro.sh): uno script nella coda di DeepSeek ferma
                    vLLM, calcola con ripresa_punteggi.py (lo strumento di T01, un processo per GPU) e riaccende vLLM
                    SEMPRE (trap): finche' lo script gira il lavoro non guarda vLLM, quindi non finisce e le GPU
                    restano nostre. Qui solo `prepara-ferma` (le coppie) e `raccogli-ferma` (punteggi ricomposti,
                    prova, file per caso); lo script lo scrive tools/ciclo_s06.sh;
     mac            il Mac con la GPU integrata (MPS), quando ha memoria;
     recas-accanto  nella coda di un lavoro di DeepSeek, ACCANTO a vLLM: il modello diviso sulle quattro GPU nella
                    memoria libera (al massimo MAX_GB_PER_GPU di pesi per scheda), solo se ogni scheda ha almeno
                    LIBERI_MIN_MB liberi; un lotto alla volta. Rischio: se vLLM avesse bisogno di memoria nuova mentre
                    il reranker la occupa, potrebbe cadere. Per questo serve il si' del PI.

   Lo stesso modello, ovunque: Qwen3-Reranker-4B alla revisione 22e683669bc0f0bd69640a1354a6d0aebcfeede5 (sul Mac la
   copia presa da ReCaS in ~/modelli/, impronte uguali ai blob di Hugging Face), i tre adattatori LoRA di T01
   (`training/lora_qwen_rr4b_<seme>/passata_2`, impronte nel registro), bfloat16, istruzione «ripresa», 2.560 token,
   media dei tre semi: come `ripresa_punteggi.punteggi`. Cambiano il dispositivo e una cosa sola nel calcolo: si
   chiedono i logit della sola ultima posizione (gli unici che servono), perche' quelli di tutte le posizioni
   (8 x 2.560 x 151.669 valori, 6 GB) non stanno ne' sul Mac ne' accanto a vLLM.

   La prova prima di fidarsi (`prova`): le stesse coppie gia' calcolate sulle H100 dal ciclo S05 (le 15.723 coppie di
   `training/principi/s05_coppie.jsonl` con `s05_punteggi_0.jsonl`, allineate riga per riga) rifatte qui, un campione a
   sorte con seme fisso. Passa con differenza media <= 0,01, massima <= 0,05 e nessuna coppia che cambia lato rispetto
   alla soglia 0,5 (R10 e suggerimenti del reranker) se non a meno di 0,05 dalla soglia. Senza prova passata la catena
   di S06 si ferma.

   Fasi:
     prova      il confronto con le H100 -> training/s06/t01_prova_<dispositivo>.json
     punteggi   le coppie di un file -> i punteggi per caso, training/principi/<caso>[_serie]_punteggi_s06.jsonl
                (una memoria per coppia, training/s06/t01_memoria.jsonl, fa ripartire senza rifare)
   Su ReCaS (recas-accanto) gira lo stesso file con --base e --dispositivo cuda-accanto.
"""
import argparse
import hashlib
import json
import pathlib
import random
import subprocess
import sys
import time

QUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(QUI/'tools'))
P = QUI/'training'/'principi'
S6 = QUI/'training'/'s06'
BASE_MAC = pathlib.Path.home()/'modelli'/'Qwen3-Reranker-4B-22e6836'
ADATTATORE = 'training/lora_qwen_rr4b_{seme}/passata_2'
SEMI = (1, 2, 3)
MAXLEN = 2560
LOTTO = 8
LOTTO_ACCANTO = 1             # accanto a vLLM: un testo alla volta, la memoria delle attivazioni resta minima
MAX_GB_PER_GPU = 2.3          # pesi per scheda accanto a vLLM (8 GB divisi su quattro)
LIBERI_MIN_MB = 4000          # sotto questa memoria libera su una scheda non si comincia
PROVA_N = 300
SOGLIA = 0.5
TOLLERANZA_MEDIA = 0.01
TOLLERANZA_MAX = 0.05


def leggi_jsonl(f):
    with open(f, encoding='utf-8') as h:
        return [json.loads(riga) for riga in h if riga.strip()]


def chiave(q, d):
    """l'impronta di una coppia: stessa domanda e stesso testo danno lo stesso punteggio"""
    return hashlib.sha256(json.dumps([q, d, MAXLEN], ensure_ascii=False).encode('utf-8')).hexdigest()


def esito_prova(nuovi, h100, soglia=SOGLIA, media_max=TOLLERANZA_MEDIA, diff_max=TOLLERANZA_MAX):
    """Il confronto fra i punteggi calcolati qui e quelli delle H100 sulle stesse coppie. Passa se la differenza media
    e' al massimo `media_max`, la massima al massimo `diff_max`, e nessuna coppia cambia lato rispetto a `soglia`, salvo
    quelle con entrambi i punteggi a meno di `diff_max` dalla soglia (li' il lato e' rumore)."""
    if len(nuovi) != len(h100) or not nuovi:
        raise ValueError('servono due elenchi della stessa lunghezza, non vuoti')
    d = [abs(a - b) for a, b in zip(nuovi, h100, strict=True)]
    lato = [(a >= soglia) != (b >= soglia) for a, b in zip(nuovi, h100, strict=True)]
    lontani = [i for i, x in enumerate(lato)
               if x and not (abs(nuovi[i] - soglia) < diff_max and abs(h100[i] - soglia) < diff_max)]
    media = sum(d) / len(d)
    return {'coppie': len(d), 'differenza_media': round(media, 5), 'differenza_massima': round(max(d), 5),
            'cambi_di_lato': sum(lato), 'cambi_di_lato_lontani_dalla_soglia': len(lontani),
            'passa': media <= media_max and max(d) <= diff_max and not lontani}


def liberi_mb():
    """la memoria libera di ogni GPU visibile, in MB (nvidia-smi)"""
    out = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True, check=True).stdout
    return [int(x) for x in out.split()]


class Riordinatore:
    """`prova_riordinatori.QwenRiordinatore` sul dispositivo scelto: 'mps', 'cpu', o 'cuda-accanto' (il modello diviso
    sulle GPU visibili, al massimo MAX_GB_PER_GPU di pesi per scheda). La classe originale scrive .cuda()."""

    def __init__(self, base, dispositivo):
        import torch
        from prova_riordinatori import PREFISSO, SUFFISSO
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(str(base), padding_side='left')
        if dispositivo == 'cuda-accanto':
            n = torch.cuda.device_count()
            self.m = AutoModelForCausalLM.from_pretrained(str(base), dtype=torch.bfloat16, device_map='auto',
                                                          max_memory={i: f'{MAX_GB_PER_GPU}GiB' for i in range(n)})
            self.dev, self.lotto = 'cuda:0', LOTTO_ACCANTO
        else:
            self.m = AutoModelForCausalLM.from_pretrained(str(base), dtype=torch.bfloat16, device_map=dispositivo)
            self.dev, self.lotto = dispositivo, LOTTO
        self.si = self.tok.convert_tokens_to_ids('yes')
        self.no = self.tok.convert_tokens_to_ids('no')
        self.pre = self.tok.encode(PREFISSO, add_special_tokens=False)
        self.suf = self.tok.encode(SUFFISSO, add_special_tokens=False)

    def con_adattatori(self):
        from peft import PeftModel
        self.m = PeftModel.from_pretrained(self.m, str(QUI/ADATTATORE.format(seme=SEMI[0])), adapter_name=f's{SEMI[0]}')
        for s in SEMI[1:]:
            self.m.load_adapter(str(QUI/ADATTATORE.format(seme=s)), adapter_name=f's{s}')
        self.m.eval()

    def codifica(self, righe, istr):
        testi = [f'<Instruct>: {istr}\n<Query>: {q}\n<Document>: {d}' for q, d in righe]
        enc = self.tok(testi, padding=False, truncation='longest_first', return_attention_mask=False,
                       max_length=MAXLEN - len(self.pre) - len(self.suf))
        enc['input_ids'] = [self.pre + ids + self.suf for ids in enc['input_ids']]
        return self.tok.pad(enc, padding=True, return_tensors='pt').to(self.dev)

    def punteggi(self, coppie, istr, seme):
        torch = self.torch
        self.m.set_adapter(f's{seme}')
        out = []
        with torch.no_grad():
            for i in range(0, len(coppie), self.lotto):
                # solo i logit dell'ultima posizione (vedi in testa): stessi numeri, 6 GB in meno
                lg = self.m(**self.codifica(coppie[i:i + self.lotto], istr), logits_to_keep=1).logits[:, -1, :]
                z = torch.log_softmax(torch.stack([lg[:, self.no], lg[:, self.si]], dim=1).float(), dim=1)
                out += z[:, 1].exp().cpu().tolist()
        return out


def leggi_memoria(memoria):
    fatte = {}
    if memoria.exists():
        with open(memoria, encoding='utf-8') as h:
            for riga in h:
                try:
                    x = json.loads(riga)
                except ValueError:
                    continue            # una riga troncata da un'interruzione
                fatte[x['k']] = x['s']
    return fatte


def calcola(coppie, base, dispositivo, memoria, ogni=200):
    """{chiave: punteggio medio dei tre semi} per le coppie (q, d); quelle gia' nella memoria non si rifanno"""
    from prova_riordinatori import ISTR
    fatte = leggi_memoria(memoria)
    da_fare, viste = [], set()
    for q, d in coppie:
        k = chiave(q, d)
        if k not in fatte and k not in viste:
            viste.add(k)
            da_fare.append((k, q, d))
    print(f'coppie {len(coppie)}, gia\' nella memoria {len(coppie) - len(da_fare)}, da fare {len(da_fare)}', flush=True)
    if da_fare:
        if dispositivo == 'cuda-accanto':
            lib = liberi_mb()
            print('memoria libera per GPU (MB):', lib, flush=True)
            if min(lib) < LIBERI_MIN_MB:
                raise SystemExit(f'memoria libera sotto {LIBERI_MIN_MB} MB su una GPU: non si comincia (prima vLLM)')
        rr = Riordinatore(base, dispositivo)
        rr.con_adattatori()
        memoria.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        with open(memoria, 'a', encoding='utf-8') as f:
            for i in range(0, len(da_fare), ogni):
                pezzo = da_fare[i:i + ogni]
                semi = [rr.punteggi([(q, d) for _, q, d in pezzo], ISTR['ripresa'], s) for s in SEMI]
                for j, (k, _, _) in enumerate(pezzo):
                    s = [x[j] for x in semi]
                    fatte[k] = sum(s) / len(s)
                    f.write(json.dumps({'k': k, 's': fatte[k], 'semi': s}) + '\n')
                f.flush()
                print(f'  {min(i + ogni, len(da_fare))}/{len(da_fare)} [{time.time() - t0:.0f}s]', flush=True)
    return {chiave(q, d): fatte[chiave(q, d)] for q, d in coppie}


def campione_prova(n, seme=20261003):
    """(coppie, punteggi delle H100) per la prova: n righe a sorte di s05_coppie.jsonl con i loro punteggi"""
    righe, h100 = leggi_jsonl(P/'s05_coppie.jsonl'), leggi_jsonl(P/'s05_punteggi_0.jsonl')
    assert len(righe) == len(h100)
    idx = sorted(random.Random(seme).sample(range(len(righe)), n))
    for i in idx:
        assert righe[i]['principio'] == h100[i]['principio']
    return [(righe[i]['q'], righe[i]['d']) for i in idx], [h100[i]['punteggio'] for i in idx]


def prova(a):
    coppie, ref = campione_prova(a.n)
    t0 = time.time()
    m = calcola(coppie, a.base, a.dispositivo, S6/f't01_memoria_prova_{a.dispositivo}.jsonl')
    nuovi = [m[chiave(q, d)] for q, d in coppie]
    e = esito_prova(nuovi, ref)
    e.update({'data': time.strftime('%Y-%m-%d %H:%M'), 'dispositivo': a.dispositivo, 'secondi': round(time.time() - t0),
              'riferimento': 'training/principi/s05_coppie.jsonl con s05_punteggi_0.jsonl (H100, ciclo S05 del 02/10)',
              'seme_del_campione': 20261003,
              'peggiori': sorted(({'nuovo': round(x, 5), 'h100': y} for x, y in zip(nuovi, ref, strict=True)),
                                 key=lambda z: -abs(z['nuovo'] - z['h100']))[:10]})
    S6.mkdir(parents=True, exist_ok=True)
    with open(S6/f't01_prova_{a.dispositivo}.json', 'w', encoding='utf-8') as h:
        json.dump(e, h, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in e.items() if k != 'peggiori'}, ensure_ascii=False, indent=1))
    return 0 if e['passa'] else 1


def scrivi_punteggi(righe, m, etichetta='s06'):
    """i punteggi per caso nei file che leggi_ripresa.prepara e carica_ripresa.py leggono"""
    import sonde
    per = {}
    for x in righe:
        per.setdefault(x['caso'], []).append(x)
    for caso, xs in per.items():
        f = P/f'{caso}{sonde.suf(caso)}_punteggi_{etichetta}.jsonl'
        with open(f, 'w', encoding='utf-8') as h:
            for x in xs:
                h.write(json.dumps({k: x[k] for k in ('riga', 'pagina_id', 'dove', 'pagina', 'principio') if k in x}
                                   | {'punteggio': round(float(m[chiave(x['q'], x['d'])]), 5)}) + '\n')
        print(caso, len(xs), 'punteggi ->', f.relative_to(QUI))


# ── recas-ferma: lo strumento di sempre (ripresa_punteggi.py) nella coda di DeepSeek, vLLM fermato e riacceso ────

FERMA_COPPIE = P/'s06_coppie.jsonl'     # ripresa_punteggi.punteggi --caso s06 legge training/principi/s06_coppie.jsonl


def coppie_ferma(righe, prova_coppie):
    """le righe per ripresa_punteggi.py: le coppie di S06 e, in coda, le coppie della prova (gia' calcolate sulle H100
    dal ciclo S05), riconoscibili da `dove` = 'prova' e `riga` = 'prova<i>'"""
    out = [dict(x) for x in righe]
    out += [{'caso': 'prova', 'riga': f'prova{i}', 'dove': 'prova', 'principio': '', 'q': q, 'd': d}
            for i, (q, d) in enumerate(prova_coppie)]
    return out


def ricomponi(coppie, pezzi):
    """{chiave: punteggio} dai file di ripresa_punteggi.punteggi: il pezzo k ha le coppie coppie[k::n], in ordine.
    Ogni riga del pezzo deve corrispondere alla coppia (stessa riga o pagina, stesso principio), altrimenti errore."""
    n, out = len(pezzi), {}
    for k, pezzo in enumerate(pezzi):
        attese = coppie[k::n]
        if len(pezzo) != len(attese):
            raise ValueError(f'pezzo {k}: {len(pezzo)} punteggi per {len(attese)} coppie')
        for x, s in zip(attese, pezzo, strict=True):
            if any(x.get(c) != s.get(c) for c in ('riga', 'pagina_id', 'principio')):
                raise ValueError(f'pezzo {k}: punteggio fuori posto ({s})')
            out[chiave(x['q'], x['d'])] = s['punteggio']
    return out


def raccogli_ferma(a):
    """dopo il calcolo su ReCaS: i punteggi ricomposti, la prova contro le H100, la memoria e i file per caso"""
    coppie = leggi_jsonl(FERMA_COPPIE)
    pezzi = [leggi_jsonl(S6/f's06_punteggi_{k}.jsonl') for k in range(a.pezzi)]
    m = ricomponi(coppie, pezzi)
    prova_coppie, ref = campione_prova(PROVA_N)
    e = esito_prova([m[chiave(q, d)] for q, d in prova_coppie], ref)
    e.update({'data': time.strftime('%Y-%m-%d %H:%M'), 'dispositivo': 'recas-ferma (H100, ripresa_punteggi.py)',
              'riferimento': 'training/principi/s05_coppie.jsonl con s05_punteggi_0.jsonl (H100, ciclo S05 del 02/10)',
              'seme_del_campione': 20261003})
    with open(S6/'t01_prova_recas-ferma.json', 'w', encoding='utf-8') as h:
        json.dump(e, h, ensure_ascii=False, indent=1)
    print('prova T01 contro le H100:', json.dumps(e, ensure_ascii=False))
    s06 = [x for x in coppie if x['caso'] != 'prova']
    with open(S6/'t01_memoria_ferma.jsonl', 'w', encoding='utf-8') as h:
        for x in s06:
            k = chiave(x['q'], x['d'])
            h.write(json.dumps({'k': k, 's': m[k]}) + '\n')
    if not e['passa']:
        return 1
    scrivi_punteggi(s06, m)
    return 0


def prepara_ferma(a):
    righe = leggi_jsonl(S6/'s06_coppie.jsonl')
    prova_coppie, _ = campione_prova(PROVA_N)
    tutte = coppie_ferma(righe, prova_coppie)
    with open(FERMA_COPPIE, 'w', encoding='utf-8') as h:
        for x in tutte:
            h.write(json.dumps(x, ensure_ascii=False) + '\n')
    print(f'{len(righe)} coppie di S06 + {len(prova_coppie)} della prova -> {FERMA_COPPIE.relative_to(QUI)}')
    return 0


def punteggi(a):
    righe = leggi_jsonl(a.coppie)
    m = calcola([(x['q'], x['d']) for x in righe], a.base, a.dispositivo, pathlib.Path(a.memoria))
    if a.solo_memoria:
        return 0                        # su ReCaS: si riporta la memoria al Mac, i file per caso li scrive il Mac
    scrivi_punteggi(righe, m)
    return 0


if __name__ == '__main__':
    import giornale  # il giornale delle operazioni: ogni esecuzione, i file, le scritture, gli errori
    giornale.avvia()
    ap = argparse.ArgumentParser()
    ap.add_argument('fase', choices=['prova', 'punteggi', 'prepara-ferma', 'raccogli-ferma'])
    ap.add_argument('--dispositivo', default='mps', choices=['mps', 'cpu', 'cuda-accanto'])
    ap.add_argument('--base', default=str(BASE_MAC), help='la cartella del modello base (revisione 22e6836)')
    ap.add_argument('--n', type=int, default=PROVA_N, help='prova: quante coppie di S05 rifare')
    ap.add_argument('--coppie', default=str(S6/'s06_coppie.jsonl'))
    ap.add_argument('--memoria', default=str(S6/'t01_memoria.jsonl'))
    ap.add_argument('--solo-memoria', action='store_true', help='punteggi: solo la memoria, non i file per caso')
    ap.add_argument('--pezzi', type=int, default=4, help='raccogli-ferma: quanti pezzi (uno per GPU)')
    a = ap.parse_args()
    sys.exit({'prova': prova, 'punteggi': punteggi, 'prepara-ferma': prepara_ferma,
              'raccogli-ferma': raccogli_ferma}[a.fase](a))
