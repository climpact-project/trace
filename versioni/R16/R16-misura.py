import json, sys, collections, random, difflib, gzip
sys.path.insert(0, '/Users/giuseppenagieri/sabin-corpus/tools')
import freni as F
R='/Users/giuseppenagieri/sabin-corpus/'
Q=R+'training/principi/'
OCR={k.split('#')[0] for k in json.load(open(R+'training/ocr/pagine_sostituite.json'))}
casi={'urgenda':'','neubauer':'P05','future-generations':'P05','klimaseniorinnen':'','cig-parere-clima':'P09','idh-oc-32-25':''}
righe_tutte={}; serve=set()
for c,s in casi.items():
    for l in open(f'{Q}{c}_ripresa_righe_{s}cinque.jsonl'):
        x=json.loads(l); righe_tutte[(c,x['id'])]=x
        for v in x['vicine']:
            serve.add(f"{x['document_id']}#p{v['pagina']}"); serve.add(f"{x['document_id']}#p{v['pagina']+1}")
testi={}
with gzip.open(R+'index/pagine/pagine.jsonl.gz','rt') as f:
    for l in f:
        x=json.loads(l)
        if x['id'] in serve: testi[x['id']]=x['testo'][:12000]
def uno(x):
    c,k,p,t,seg,ocr=x
    if not F.prova_trovata(p,t,True): return 'N'
    return 'T->T' if F.prova_intera(p,t,seg,ocr) else 'T->N'
n=collections.Counter(); giu=[]; TUTTI=[]
for c,s in casi.items():
    for l in open(f'{Q}{c}_ripresa_deepseek_{s}cinque.jsonl'):
        try: x=json.loads(l)
        except: continue
        r=righe_tutte.get((c,x['id']))
        if not r: continue
        d=r['document_id']; ocr=d in OCR
        pag={}
        for v in r['vicine']:
            t=v['testo']; full=testi.get(f"{d}#p{v['pagina']}",'')
            if full.startswith(t[:200]) and len(full)>len(t): t=full
            pag[v['pagina']]=(t, testi.get(f"{d}#p{v['pagina']+1}",''))
        for y in x.get('letture') or []:
            if not isinstance(y,dict): continue
            items=[]
            if y.get('frase_sostenuta'): items.append(('frase',str(y['frase_sostenuta']),r['contesto'],''))
            for v in y.get('vicine') or []:
                if isinstance(v,dict) and v.get('prova') and v.get('pagina') in pag: items.append(('prova',str(v['prova']),*pag[v['pagina']]))
            for k,p,t,seg in items:
                TUTTI.append((c,k,p,t,seg,ocr))
import multiprocessing as mp
with mp.get_context("fork").Pool(12) as pool:
    ris=pool.map(uno, TUTTI, chunksize=200)
for (c,k,p,t,seg,ocr),e in zip(TUTTI,ris):
    n[(c,k,e)]+=1
    if e=='T->N': giu.append((c,k,p,t,seg))
tab=collections.defaultdict(dict)
for (c,k,e),v in n.items(): tab[f'{c} {k}'][e]=v
for k in sorted(tab): print(k, tab[k])
print('T->N totale', sum(v for (c,k,e),v in n.items() if e=='T->N'), 'T totale', sum(v for (c,k,e),v in n.items() if e!='N'))
random.seed(19)
out=[]
for c,k,p,t,seg in random.sample(giu,20):
    pn=F._n16(p); tn=F._n16(t+' '+seg)
    sm=difflib.SequenceMatcher(None,pn,tn,autojunk=False); m=sm.find_longest_match(0,len(pn),0,len(tn))
    out.append({'caso':c,'cosa':k,'prova':pn,'pagina':tn[max(0,m.b-m.a):max(0,m.b-m.a)+len(pn)+120]})
json.dump(out,open('R16-campione-20.json','w'),ensure_ascii=False,indent=1)
