"""Reranker comparison: more context, and a larger reranker.

   The reranker reads a proposition and a passage together and scores whether the passage takes up the
   proposition. The baseline is `bge-reranker-v2-m3` (568M parameters) fine-tuned on team judgments:
   AUC 0.756 on the 137 test rows. Two experiments:

     1. More context. Scoring the full page instead of a fragment accounted for almost half of the earlier
        gain. This tests whether the page plus the next one, or plus the previous and next, helps further,
        using the five adapters trained on the corrected labels, without retraining.
     2. A larger reranker. `Qwen3-Reranker` (4B and 8B) is built on an LLM and accepts an instruction.
        Evaluated zero-shot, with the default instruction and with one that asks for uptake of the reasoning
        rather than topical similarity; then fine-tuned with LoRA on the 263 training rows, three seeds.

   All results use the same 137 test rows, corrected labels and the same frozen split. No test row is ever
   used for training.

   Usage:  python tools/prova_riordinatori.py [--parti contesto,qwen_zero,qwen_lora,qwen4_salva]
   Scores are appended to training/prova_riordinatori.json.
"""
import argparse, gc, json, pathlib, time
import numpy as np
import torch

QUI = pathlib.Path(__file__).resolve().parent.parent
BGE = 'BAAI/bge-reranker-v2-m3'
ISTR = {
    'di_serie': 'Given a web search query, retrieve relevant passages that answer the query',
    'ripresa': ('Judge whether the Document adopts, as its own reasoning, the legal proposition '
                'in the Query as established in the cited judgment, rather than merely discussing '
                'the same topic or deriving a similar conclusion from other legal sources such as '
                'treaties, national constitutions, regional human rights instruments or other cases.'),
}


def carica(parte):
    p = QUI/'training'/f'urgenda_decisione_{parte}_corrette_larghe.jsonl'
    return [x for x in (json.loads(r) for r in p.read_text(encoding='utf-8').splitlines() if r.strip())
            if x['frammento'] and x.get('finestra_larga')]


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s, float)
    o = np.argsort(s); r = np.empty(len(s)); r[o] = np.arange(1, len(s)+1)
    for v in np.unique(s):
        m = s == v
        if m.sum() > 1:
            r[m] = r[m].mean()
    p, n = y.sum(), len(y)-y.sum()
    return float((r[y == 1].sum()-p*(p+1)/2)/(p*n)) if p and n else float('nan')


def prime(y, s, k):
    return float(np.asarray(y)[np.argsort(-np.asarray(s, float))[:k]].mean())


def bootstrap(y, a, b, n=4000, seme=20260923):
    rng = np.random.default_rng(seme); y = np.asarray(y); a = np.asarray(a); b = np.asarray(b)
    d = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() in (0, len(y)):
            continue
        d.append(auc(y[i], b[i]) - auc(y[i], a[i]))
    d = np.array(d)
    return float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)), float((d <= 0).mean())


def riga(nome, y, s, base=None):
    out = f'  {nome:62s} AUC {auc(y, s):.3f}   prime 20 {100*prime(y, s, 20):3.0f}%   prime 40 {100*prime(y, s, 40):3.0f}%'
    if base is not None:
        lo, hi, pg = bootstrap(y, base, s)
        out += f'   | {auc(y, s)-auc(y, base):+.3f} [{lo:+.3f}, {hi:+.3f}]'
    print(out, flush=True)


# ── bge ────────────────────────────────────────────────────────────────

def bge_punteggi(adattatore, coppie, maxlen, lotto=8):
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    tok = AutoTokenizer.from_pretrained(BGE)
    m = AutoModelForSequenceClassification.from_pretrained(BGE, torch_dtype=torch.bfloat16)
    if adattatore:
        from peft import PeftModel
        m = PeftModel.from_pretrained(m, str(adattatore))
    m = m.cuda().eval(); out = []
    with torch.no_grad():
        for i in range(0, len(coppie), lotto):
            g = coppie[i:i+lotto]
            e = tok([x[0] for x in g], [x[1] for x in g], padding=True, truncation='only_second',
                    max_length=maxlen, return_tensors='pt').to('cuda')
            out += torch.sigmoid(m(**e).logits.reshape(-1).float()).cpu().tolist()
    del m; gc.collect(); torch.cuda.empty_cache()
    return np.array(out)


# ── Qwen3-Reranker ─────────────────────────────────────────────────────

PREFISSO = ("<|im_start|>system\nJudge whether the Document meets the requirements based on the Query "
            "and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n")
SUFFISSO = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"


class QwenRiordinatore:
    def __init__(self, nome, lora=None):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        self.tok = AutoTokenizer.from_pretrained(nome, padding_side='left')
        self.m = AutoModelForCausalLM.from_pretrained(nome, torch_dtype=torch.bfloat16).cuda()
        self.si = self.tok.convert_tokens_to_ids('yes'); self.no = self.tok.convert_tokens_to_ids('no')
        self.pre = self.tok.encode(PREFISSO, add_special_tokens=False)
        self.suf = self.tok.encode(SUFFISSO, add_special_tokens=False)

    def codifica(self, righe, istr, maxlen):
        testi = [f'<Instruct>: {istr}\n<Query>: {q}\n<Document>: {d}' for q, d in righe]
        enc = self.tok(testi, padding=False, truncation='longest_first', return_attention_mask=False,
                       max_length=maxlen - len(self.pre) - len(self.suf))
        enc['input_ids'] = [self.pre + ids + self.suf for ids in enc['input_ids']]
        return self.tok.pad(enc, padding=True, return_tensors='pt').to('cuda')

    def logit_si_no(self, enc):
        lg = self.m(**enc).logits[:, -1, :]
        return torch.stack([lg[:, self.no], lg[:, self.si]], dim=1).float()

    def punteggi(self, coppie, istr, maxlen, lotto=4):
        self.m.eval(); out = []
        with torch.no_grad():
            for i in range(0, len(coppie), lotto):
                z = torch.log_softmax(self.logit_si_no(self.codifica(coppie[i:i+lotto], istr, maxlen)), dim=1)
                out += z[:, 1].exp().cpu().tolist()
        return np.array(out)

    def libera(self):
        del self.m; gc.collect(); torch.cuda.empty_cache()


def addestra_qwen(nome, tr, te, y_te, istr, maxlen, seme, epoche=3, lotto=4, lr=1e-4, rango=16, salva=None):
    """LoRA fine-tuning of a Qwen reranker. The loss is cross-entropy over the two
    "no"/"yes" logits at the last position, i.e. exactly the score the model
    produces at inference. Three epochs, as in the bge training protocol."""
    from peft import LoraConfig, get_peft_model
    torch.manual_seed(seme); rnd = np.random.default_rng(seme)
    q = QwenRiordinatore(nome)
    q.m.gradient_checkpointing_enable(); q.m.config.use_cache = False
    q.m = get_peft_model(q.m, LoraConfig(r=rango, lora_alpha=2*rango, lora_dropout=0.05,
                                         target_modules=['q_proj', 'k_proj', 'v_proj', 'o_proj'],
                                         task_type='CAUSAL_LM'))
    q.m.enable_input_require_grads()
    opt = torch.optim.AdamW([p for p in q.m.parameters() if p.requires_grad], lr=lr)
    coppie_te = [(x['sonda_testo'], x['finestra']) for x in te]
    for ep in range(epoche):
        q.m.train(); idx = rnd.permutation(len(tr)); somma = 0.0
        for j in range(0, len(idx), lotto):
            g = [tr[i] for i in idx[j:j+lotto]]
            enc = q.codifica([(x['sonda_testo'], x['finestra']) for x in g], istr, maxlen)
            et = torch.tensor([x['etichetta'] for x in g], device='cuda')
            l = torch.nn.functional.cross_entropy(q.logit_si_no(enc), et)
            l.backward(); opt.step(); opt.zero_grad(); somma += l.item()*len(g)
        s = q.punteggi(coppie_te, istr, maxlen)
        riga(f'    {nome.split("/")[-1]} LoRA seme {seme} dopo passata {ep+1} (perdita {somma/len(tr):.3f})', y_te, s)
        if salva:
            # Save the adapter and its test scores after every epoch, so that an
            # interrupted job does not lose the weights.
            q.m.save_pretrained(str(salva/f'passata_{ep+1}'))
            (salva/f'passata_{ep+1}'/'punteggi_prova.json').write_text(json.dumps(s.tolist()), encoding='utf-8')
    q.libera()
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--parti', default='contesto,qwen_zero,qwen_lora')
    a = ap.parse_args()
    tr, te = carica('addestramento'), carica('prova')
    y_te = np.array([x['etichetta'] for x in te])
    print(f'prova {len(te)} righe ({y_te.sum()} vere) | addestramento {len(tr)}', flush=True)
    esiti = {}
    ad = [QUI/'training'/f'lora_riordino_corrette_{s}' for s in range(1, 6)]

    if 'contesto' in a.parti:
        print('\n══ 1. bge addestrato, piu\' contesto (i cinque adattatori delle etichette corrette, insieme) ══', flush=True)
        base = None
        for campo, maxlen in (('finestra', 2304), ('pagina_piu_mezza', 4096), ('finestra_larga', 6144)):
            t0 = time.time()
            S = np.mean([bge_punteggi(p, [(x['sonda_testo'], x[campo]) for x in te], maxlen) for p in ad], axis=0)
            if base is None:
                base = S
            esiti[f'bge_addestrato_{campo}'] = S.tolist()
            riga(f'bge addestrato, {campo} ({maxlen} token) [{time.time()-t0:.0f}s]', y_te, S, None if campo == 'finestra' else base)
        S0 = bge_punteggi(None, [(x['sonda_testo'], x['finestra_larga']) for x in te], 6144)
        riga('bge NON addestrato, finestra_larga (6144 token)', y_te, S0, base)
        esiti['base_bge'] = base.tolist()

    base_bge = np.array(esiti['base_bge']) if 'base_bge' in esiti else None
    if base_bge is None and (QUI/'training'/'prova_riordinatori.json').exists():
        base_bge = np.array(json.loads((QUI/'training'/'prova_riordinatori.json').read_text()).get('base_bge'))
    if 'qwen_zero' in a.parti:
        print('\n══ 2. Qwen3-Reranker cosi\' com\'e\', sulla pagina ══', flush=True)
        for nome in ('Qwen/Qwen3-Reranker-4B', 'Qwen/Qwen3-Reranker-8B'):
            t0 = time.time(); q = QwenRiordinatore(nome)
            for k, istr in ISTR.items():
                s = q.punteggi([(x['sonda_testo'], x['finestra']) for x in te], istr, 2560)
                esiti[f'{nome}_{k}'] = s.tolist()
                riga(f'{nome.split("/")[-1]}, istruzione {k} [{time.time()-t0:.0f}s]', y_te, s, base_bge)
            q.libera()

    if 'qwen4_salva' in a.parti:
        print('\n══ 4. Qwen3-Reranker-4B addestrato, CON salvataggio dei pesi, tre semi ══', flush=True)
        for seme in (1, 2, 3):
            cart = QUI/'training'/f'lora_qwen_rr4b_{seme}'
            cart.mkdir(parents=True, exist_ok=True)
            addestra_qwen('Qwen/Qwen3-Reranker-4B', tr, te, y_te, ISTR['ripresa'], 2560, seme, salva=cart)
        for ep in (1, 2, 3):
            M = np.mean([json.loads((QUI/'training'/f'lora_qwen_rr4b_{s}'/f'passata_{ep}'/'punteggi_prova.json').read_text())
                         for s in (1, 2, 3)], axis=0)
            riga(f'Qwen3-Reranker-4B LoRA, tre semi insieme, dopo {ep} passate', y_te, M, base_bge)

    if 'qwen_lora' in a.parti:
        print('\n══ 3. Qwen3-Reranker addestrato (LoRA, tre passate, tre semi) ══', flush=True)
        for nome in ('Qwen/Qwen3-Reranker-4B', 'Qwen/Qwen3-Reranker-8B'):
            fin = []
            for seme in (1, 2, 3):
                fin.append(addestra_qwen(nome, tr, te, y_te, ISTR['ripresa'], 2560, seme))
            M = np.mean(fin, axis=0); esiti[f'{nome}_lora_insieme'] = M.tolist()
            riga(f'{nome.split("/")[-1]} LoRA, i tre semi insieme', y_te, M, base_bge)

    if esiti:
        vecchio = QUI/'training'/'prova_riordinatori.json'
        prima = json.loads(vecchio.read_text()) if vecchio.exists() else {}
        vecchio.write_text(json.dumps({**prima, 'ids': [x['id'] for x in te], **esiti}), encoding='utf-8')


if __name__ == '__main__':
    main()
