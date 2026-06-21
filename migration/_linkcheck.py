#!/usr/bin/env python3
"""Liveness-check every URL in index.json. Flags only hard failures
(404/410/DNS/timeout/connreset). Treats 403/405/406/429 as 'reachable but
bot-blocked' (common for avnet/store pages)."""
import os, json, concurrent.futures as cf, urllib.request, urllib.error, ssl, collections

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(_root, "index.json"), encoding="utf-8"))
urls = collections.OrderedDict()
def add(u, ctxlabel):
    if u and u.startswith("http"): urls.setdefault(u, ctxlabel)
for b in d["facets"]["boards"]:
    add(b.get("image"), f"img:{b['partNumber']}"); add(b.get("link"), f"prod:{b['partNumber']}")
    add(b.get("buy"), f"buy:{b['partNumber']}")
    for r in b.get("resources", []): add(r["url"], f"{r['kind']}:{b['partNumber']}")
for p in d["partners"]: add(p.get("info"), f"info:{p['name']}")
for r in d["repos"]:
    add(r.get("url"), f"repo:{r.get('repo') or r['displayName']}")

def check(u):
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(u, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 406, 429) and method == "HEAD":
                continue  # retry with GET
            return e.code
        except Exception as e:
            if method == "HEAD":
                continue
            return type(e).__name__
    return "ERR"

results = {}
with cf.ThreadPoolExecutor(max_workers=16) as ex:
    futs = {ex.submit(check, u): u for u in urls}
    for f in cf.as_completed(futs):
        results[futs[f]] = f.result()

OK_SOFT = {403, 405, 406, 429}
hard, soft = [], []
for u, label in urls.items():
    s = results[u]
    if s == 200 or s == 301 or s == 302 or s == 303 or s == 307 or s == 308:
        continue
    elif s in OK_SOFT:
        soft.append((s, label, u))
    else:
        hard.append((s, label, u))

print(f"checked {len(urls)} unique URLs")
print(f"HARD failures (need attention): {len(hard)}")
for s, label, u in sorted(hard, key=lambda x: str(x[0])):
    print(f"  [{s}] {label}\n        {u}")
print(f"\nsoft/bot-blocked (likely fine): {len(soft)}")
for s, label, u in sorted(soft, key=lambda x: str(x[0]))[:40]:
    print(f"  [{s}] {label}")
