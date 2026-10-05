#!/usr/bin/env python3
"""
Scarica i documenti del Climate Litigation Database (Sabin Center / Climate Policy Radar)
a partire dal dump ufficiale dell'intero database.

Solo stdlib: gira con qualsiasi python3 >= 3.9.

  python3 fetch_sabin.py --metadata metadata.csv --out ~/sabin-corpus --rps 1.0

Riprendibile: rilanciando lo stesso comando salta quanto gia' scaricato e verificato.

Correzioni del 04/10/2026 (D05; audit del 04/10: 134 indirizzi mai scaricati, 4 memorie africane date per fatte):
  - "gia' fatto" vale per la COPPIA (document_id, indirizzo) e solo per righe scaricate davvero (http 200), dal
    manifest e dai supplementi (manifest_supplemento_*.jsonl). Prima valeva l'indirizzo: un atto che EREDITAVA
    l'indirizzo di un atto rinumerato risultava fatto senza che nessuno avesse scaricato per lui;
  - mai piu' una riga "http: 0" con l'impronta del file che c'era: se il nome e' occupato si sceglie un nome nuovo
    (`__<8 cifre di sha256(url)>`, poi `__<8 cifre di sha256(url|document_id)>`), il file si crea in esclusiva
    (.part e os.link, che fallisce se il nome esiste) e non si scrive mai sopra un file;
  - se i byte scaricati sono identici a un file gia' scaricato e verificato (stessa impronta, file presente con
    quell'impronta) non si tiene una seconda copia: la riga punta a quel file e lo dice (`stessi_byte_di`);
  - 403/404/410 si riprovano UNA volta dopo una pausa (--pausa-4xx, default 30 s); i fallimenti vanno in
    failures.tsv con data, codice http, tentativi e identificativi degli atti (le prime tre colonne restano
    indirizzo, percorso, errore, come prima).
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CONTACT = "giuseppe.naglieri@uniba.it"
UA = f"CLIMPACT-research/1.0 (Universita di Bari; {CONTACT})"

stop = False


def on_sigint(signum, frame):
    global stop
    if stop:
        print("\n[!] Seconda interruzione: esco subito.", flush=True)
        sys.exit(130)
    stop = True
    print("\n[!] Interruzione richiesta: chiudo dopo il file corrente. Ctrl-C di nuovo per uscire subito.", flush=True)


signal.signal(signal.SIGINT, on_sigint)


class RateLimiter:
    """Tetto globale di richieste al secondo, condiviso da tutti i worker."""

    def __init__(self, rps):
        self.interval = 1.0 / rps if rps and rps > 0 else 0.0
        self.lock = threading.Lock()
        self.next_slot = 0.0

    def wait(self):
        if not self.interval:
            return
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next_slot)
            self.next_slot = slot + self.interval
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)


def slug(text, maxlen=70):
    text = re.sub(r"[^\w\s-]", "", str(text or ""), flags=re.UNICODE).strip()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:maxlen].strip("-").lower() or "untitled"


def safe_component(text, maxlen=80):
    """Sanitizza un componente di path mantenendolo riconoscibile."""
    text = str(text or "unknown").strip()
    text = re.sub(r"[/\\:\x00-\x1f]", "_", text)
    text = text.strip(". ")
    return (text[:maxlen] or "unknown")


def load_tasks(metadata_path):
    """Una voce per URL unico; raccoglie i documenti che la condividono."""
    by_url = {}
    with open(metadata_path, newline="", encoding="utf8") as f:
        for row in csv.DictReader(f):
            url = (row.get("Document Content URL") or "").strip()
            if not url.lower().startswith("http"):
                continue
            entry = by_url.setdefault(url, {"url": url, "docs": []})
            entry["docs"].append({
                "document_id": row.get("Document ID", ""),
                "case_id": row.get("Case ID", ""),
                "case_name": row.get("Case Name", ""),
                "title": row.get("Document Title", ""),
                "filing_date": row.get("Document Filing Date", ""),
                "jurisdictions": row.get("Jurisdictions", ""),
                "geography_isos": row.get("Geography ISOs", ""),
            })
    tasks = list(by_url.values())
    # Assegna i percorsi, poi disambigua le collisioni: Document ID diversi possono
    # ridursi allo stesso nome una volta troncati, e due URL distinti che finiscono
    # sullo stesso path si sovrascriverebbero a vicenda.
    seen = {}
    for t in tasks:
        d = t["docs"][0]
        ext = os.path.splitext(t["url"].split("?")[0])[1].lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,5}", ext or ""):
            ext = ".pdf"
        case_dir = safe_component(d["case_id"] or "no-case")
        stem = f"{safe_component(d['document_id'] or 'nodoc', 60)}__{slug(d['title'])}"
        rel = Path("documents") / case_dir / f"{stem}{ext}"
        if str(rel) in seen:
            tag = hashlib.sha256(t["url"].encode()).hexdigest()[:8]
            rel = Path("documents") / case_dir / f"{stem}__{tag}{ext}"
        seen[str(rel)] = t["url"]
        t["relpath"] = str(rel)
    return tasks


def load_done(out):
    """(coppie (document_id, url) scaricate davvero, impronta -> percorso verificato).

    Solo righe "ok" con http 200 (le "http: 0" del 19/09 portano l'impronta di un altro file), dal manifest e dai
    supplementi."""
    coppie, impronte = set(), {}
    for mp in [out / "manifest.jsonl"] + sorted(out.glob("manifest_supplemento_*.jsonl")):
        if not mp.exists():
            continue
        with open(mp, encoding="utf8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("status") != "ok" or rec.get("http") != 200:
                    continue
                for d in rec.get("docs") or []:
                    coppie.add((d.get("document_id", ""), rec["url"]))
                if rec.get("sha256") and rec.get("path"):
                    impronte.setdefault(rec["sha256"], rec["path"])
    return coppie, impronte


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def free_path(out, rel, url, doc_id):
    """Un nome libero: quello di sempre, poi con le 8 cifre dell'indirizzo, poi con quelle di indirizzo+atto."""
    rel = Path(rel)
    cands = [rel,
             rel.with_name(f"{rel.stem}__{hashlib.sha256(url.encode()).hexdigest()[:8]}{rel.suffix}"),
             rel.with_name(f"{rel.stem}__{hashlib.sha256((url + '|' + doc_id).encode()).hexdigest()[:8]}{rel.suffix}")]
    for c in cands:
        if not (out / c).exists() and not (out / c).with_name(c.name + ".part").exists():
            return c
    raise IOError(f"nessun nome libero per {rel}")


class FetchError(IOError):
    def __init__(self, msg, http=None, attempts=0):
        super().__init__(msg)
        self.http, self.attempts = http, attempts


def fetch(url, tmp, timeout=120, attempts=4, pausa_4xx=30.0):
    """Scarica in `tmp` (creazione esclusiva). Ritorna (bytes, sha256, http_status, content_type).

    403/404/410: un solo nuovo tentativo dopo `pausa_4xx` secondi (a luglio molti 403 erano transitori);
    400/401: subito fuori; 429 e 5xx: fino a `attempts` tentativi con attesa crescente."""
    last_err, last_code, ritentato_4xx = None, None, False
    attempt = 0
    while attempt < attempts:
        attempt += 1
        if stop:
            raise KeyboardInterrupt
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/pdf,application/octet-stream,*/*",
            })
            tmp.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            total = 0
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "xb") as out:
                status = resp.status
                ctype = resp.headers.get("Content-Type", "")
                clen = resp.headers.get("Content-Length")
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    h.update(chunk)
                    total += len(chunk)
            if total == 0:
                tmp.unlink(missing_ok=True)
                raise IOError("risposta vuota")
            if clen and clen.isdigit() and int(clen) != total:
                tmp.unlink(missing_ok=True)
                raise IOError(f"troncato: {total} byte contro Content-Length {clen}")
            return total, h.hexdigest(), status, ctype
        except urllib.error.HTTPError as e:
            tmp.unlink(missing_ok=True)
            last_err, last_code = f"HTTP {e.code}", e.code
            if e.code in (400, 401):
                raise FetchError(last_err, e.code, attempt)
            if e.code in (403, 404, 410):
                if ritentato_4xx:
                    raise FetchError(last_err, e.code, attempt)
                ritentato_4xx = True
                attempts = max(attempts, attempt + 1)
                wait = pausa_4xx
            else:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                wait = float(retry_after) if (retry_after or "").isdigit() else min(60, 2 ** attempt)
        except FileExistsError:
            raise
        except (urllib.error.URLError, IOError, TimeoutError) as e:
            tmp.unlink(missing_ok=True)
            last_err, last_code = str(e), None
            wait = min(60, 2 ** attempt)
        if attempt < attempts:
            time.sleep(wait + random.uniform(0, 1))
    raise FetchError(last_err or "fallito", last_code, attempt)


HOSTS = ("climatecasechart.com", "www.climatecasechart.com")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rps", type=float, default=1.0, help="tetto globale richieste/secondo (default 1.0)")
    ap.add_argument("--workers", type=int, default=1, help="download in parallelo (default 1)")
    ap.add_argument("--limit", type=int, default=0, help="scarica al massimo N file (0 = tutti)")
    ap.add_argument("--pausa-4xx", type=float, default=30.0, help="attesa prima dell'unico nuovo tentativo su 403/404/410")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    out = Path(os.path.expanduser(args.out))
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.jsonl"
    failures_path = out / "failures.tsv"

    tasks = load_tasks(args.metadata)
    done, impronte = load_done(out)
    # 04/10/2026: solo i file del Climate Litigation Database; gli indirizzi altrove (per esempio il segnaposto
    # cdn.climatepolicyradar.org/.../Litigation-404.pdf, condiviso da centinaia di atti senza file) si contano e basta
    fuori = [t for t in tasks if urllib.parse.urlsplit(t["url"]).hostname not in HOSTS]
    tasks = [t for t in tasks if urllib.parse.urlsplit(t["url"]).hostname in HOSTS]
    pending = [t for t in tasks if any((d["document_id"], t["url"]) not in done for d in t["docs"])]

    print(f"Documenti nel file ........ {sum(len(t['docs']) for t in tasks)}")
    print(f"URL unici ................. {len(tasks)}")
    print(f"Fuori dal sito (saltati) .. {len(fuori)} URL, {sum(len(t['docs']) for t in fuori)} documenti")
    print(f"Coppie gia' scaricate ..... {len(done)} (atto, URL) con http 200")
    print(f"Da scaricare .............. {len(pending)}")
    print(f"Destinazione .............. {out}")
    print(f"Ritmo ..................... {args.rps} req/s max, {args.workers} worker")
    if args.dry_run:
        for t in pending[:10]:
            print("  ", t["relpath"])
        print("(dry-run: nessun download)")
        return

    limiter = RateLimiter(args.rps)
    counters = {"ok": 0, "same": 0, "failed": 0, "bytes": 0, "seen": 0}
    started = time.time()
    budget = args.limit or len(pending)
    work = pending[:budget]

    io_lock = threading.Lock()   # protegge manifest, failures, impronte e contatori
    mf = open(manifest_path, "a", encoding="utf8")
    ff = open(failures_path, "a", encoding="utf8")

    def record(rec):
        with io_lock:
            mf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            mf.flush()

    def bump(**kw):
        with io_lock:
            for k, v in kw.items():
                counters[k] += v
            i = counters["seen"]
            if i % 25 == 0 or i == budget:
                el = time.time() - started
                rate = i / el if el else 0
                eta = (budget - i) / rate / 3600 if rate else 0
                print(f"[{i}/{budget}] ok={counters['ok']} stessi-byte={counters['same']} "
                      f"fail={counters['failed']} {counters['bytes']/1e9:.2f} GB  "
                      f"{rate:.2f}/s  ETA {eta:.1f} h", flush=True)

    def handle(t):
        if stop:
            return
        ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        doc0 = t["docs"][0]["document_id"]
        with io_lock:
            rel = free_path(out, t["relpath"], t["url"], doc0)
            tmp = out / rel.with_name(rel.name + ".part")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            open(tmp, "xb").close()          # prenota il nome: un altro worker non lo prende
        tmp.unlink()
        limiter.wait()
        try:
            n, h, status, ctype = fetch(t["url"], tmp, pausa_4xx=args.pausa_4xx)
        except KeyboardInterrupt:
            return
        except Exception as e:
            code = getattr(e, "http", None)
            tent = getattr(e, "attempts", 0)
            ids = ";".join(d["document_id"] for d in t["docs"])
            with io_lock:
                ff.write(f"{t['url']}\t{t['relpath']}\t{e}\t{ts}\thttp={code}\ttentativi={tent}\t{ids}\n")
                ff.flush()
            print(f"  FALLITO {e} ({tent} tentativi): {t['url']}", flush=True)
            bump(failed=1, seen=1)
            return
        rec = {"url": t["url"], "bytes": n, "sha256": h, "status": "ok", "http": status,
               "content_type": ctype, "docs": t["docs"], "ts": ts, "user_agent": UA}
        with io_lock:
            gemello = impronte.get(h)
            if gemello and (out / gemello).exists() and sha_file(out / gemello) == h:
                # stessi byte di un file gia' scaricato e verificato: niente seconda copia
                tmp.unlink(missing_ok=True)
                rec.update({"path": gemello, "stessi_byte_di": gemello})
                same = True
            else:
                dest = out / rel
                os.link(tmp, dest)            # fallisce se il nome esiste: mai sopra un file
                tmp.unlink()
                rec["path"] = str(rel)
                impronte.setdefault(h, str(rel))
                same = False
        record(rec)
        bump(ok=0 if same else 1, same=1 if same else 0, bytes=n, seen=1)

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(handle, work))
    finally:
        mf.close()
        ff.close()

    print(f"\nFine. scaricati={counters['ok']} stessi-byte-di-un-file-gia-presente={counters['same']} "
          f"falliti={counters['failed']} {counters['bytes']/1e9:.2f} GB")
    print(f"Manifest: {manifest_path}")
    if counters["failed"]:
        print(f"Fallimenti: {failures_path}")


if __name__ == "__main__":
    try:  # il giornale delle operazioni (tools/giornale.py), se c'e'
        sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
        import giornale
        giornale.avvia()
    except Exception:
        pass
    main()
