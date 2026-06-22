#!/usr/bin/env python3
"""
build_site.py — reads the data/*.csv catalog and produces:
  - index.json   (what the page renders)
  - AUDIT.md     (gap report: missing boards, orphan boards, image gaps,
                  uncatalogued org repos, incomplete listings)

Source: data/listings.csv, data/boards.csv, data/resources.csv, data/config.csv
(each is one editable, git-diffable sheet — see data/README.md).

Run locally:           python build_site.py
In CI with live facts:  GITHUB_TOKEN=xxx python build_site.py
"""
import os, re, csv, json, sys, urllib.request, datetime

DATA  = os.environ.get("CATALOG_DIR", "data")
OUT   = os.environ.get("OUT_DIR", ".")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Tidy a few legacy/free-text topic tags into the controlled vocabulary.
TOPIC_NORM = {
    "edge-ai": "edge-ai", "ev charging": "ev-charging", "fall_det": "fall-detection",
    "gesture_det": "gesture", "siren_det": "siren-detection", "human_activity": "human-activity",
    "uavoperations": "uav", "enviro-sense": "sensors",
}
# Topics dropped everywhere: every sample provides these, so they're noise as filters.
DROP_TOPICS = {"telemetry", "commands", "ota", "twin"}

def slug(s): return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-') or "x"
def split(s): return [x.strip() for x in str(s or "").replace(";", ",").split(",") if x.strip()]

def read_csv(name):
    """Read data/<name>.csv -> (list of row-dicts, header list). Missing file -> ([], [])."""
    path = os.path.join(DATA, f"{name}.csv")
    if not os.path.exists(path):
        return [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        hdr = rd.fieldnames or []
        rows = [r for r in rd if any((v or "").strip() for v in r.values())]
    return rows, hdr

cfg = {r["Key"]: r["Value"] for r in read_csv("config")[0] if r.get("Key")}
ORG            = os.environ.get("ORG", cfg.get("ORG", "avnet-iotconnect"))
IMAGE_BASE     = cfg.get("IMAGE_BASE", "")
IMAGE_LOCAL    = cfg.get("IMAGE_LOCAL_BASE", "assets/boards/")
BRAND_BASE     = cfg.get("BRAND_BASE", "assets/brand/")
DEFAULT_STATUS = cfg.get("DEFAULT_STATUS", "beta")
PAGES_URL      = cfg.get("PAGES_URL", "")

def resolve_image(v):
    if not v: return None
    s = str(v).strip()
    if re.match(r'^(https?:|data:|//)', s): return s
    return (IMAGE_BASE or "") + s

# Silicon vendors with brand logos shown in the partner showcase.
PARTNER_LOGO = {
    "STMicroelectronics": "st-logo.png", "Infineon": "infineon-logo.png",
    "Microchip": "microchip-logo.png", "NXP": "nxp-logo.png", "Renesas": "renesas-logo.png",
    "AMD": "amd-logo.svg", "NVIDIA": "nvidia-logo.svg", "Intel": "intel-logo.svg",
    "Qualcomm": "qualcomm-logo.svg",
}
# ---------- Resources ----------
res_rows, _ = read_csv("resources")
res_by_board = {}     # pn(lower) -> [ {kind,title,url} ]
res_by_mfr   = {}     # manufacturer -> [ {kind,title,url} ]
for r in res_rows:
    ref = str(r.get("Ref") or "").strip()
    url = str(r.get("URL") or "").strip()
    if not ref or not url: continue
    item = {"kind": str(r.get("Kind") or "doc").strip().lower(),
            "title": str(r.get("Title") or "").strip(), "url": url}
    if str(r.get("RefType") or "board").strip().lower() == "manufacturer":
        res_by_mfr.setdefault(ref, []).append(item)
    else:
        res_by_board.setdefault(ref.lower(), []).append(item)

# ---------- Boards ----------
brows, _ = read_csv("boards")
board_defs = {}; boards_by_pn = {}; boards_by_name = {}
for row in brows:
    if str(row.get("Include") or "yes").lower() == "no": continue
    pn = str(row.get("Part Number") or "").strip()
    nm = str(row.get("Board Name") or "").strip()
    if not (pn or nm): continue
    sg = slug(pn or nm)
    quals = []
    if str(row.get("AWS Qualified") or "").lower() == "yes": quals.append("AWS Qualified")
    if str(row.get("Greengrass") or "").lower() == "yes": quals.append("Greengrass")
    img_local = str(row.get("Image Local") or "").strip()
    res = sorted(res_by_board.get(pn.lower(), []),
                 key=lambda x: ["buy","quickstart","developer","demo","webinar","video","blog","doc","info"].index(x["kind"])
                 if x["kind"] in ["buy","quickstart","developer","demo","webinar","video","blog","doc","info"] else 99)
    buy = next((x["url"] for x in res if x["kind"] == "buy"), None)
    integrator = str(row.get("Manufacturer") or "Other").strip()
    silicon = str(row.get("Silicon") or "").strip() or integrator   # vendor = silicon (chip maker)
    d = {"slug": sg, "vendor": silicon, "integrator": integrator,
         "name": nm or pn, "partNumber": pn,
         "image": resolve_image(row.get("Image File")),
         "imageLocal": (IMAGE_LOCAL + img_local) if img_local else None,
         "link": str(row.get("Product Link") or "").strip() or None,
         "buy": buy, "qualifications": quals, "tags": split(row.get("Tags")),
         "resources": res}
    board_defs[sg] = d
    if pn: boards_by_pn[pn.lower()] = sg
    if nm: boards_by_name[nm.lower()] = sg

# ---------- Listings ----------
lrows, _ = read_csv("listings")
missing_boards = {}
def resolve_ref(ref, listing_name):
    k = ref.lower()
    if k in boards_by_pn:  return boards_by_pn[k]
    if k in boards_by_name: return boards_by_name[k]
    missing_boards.setdefault(ref, set()).add(listing_name)
    sg = "x-" + slug(ref)
    board_defs.setdefault(sg, {"slug": sg, "vendor": "Other", "integrator": "Other", "name": ref, "partNumber": "",
                               "image": None, "imageLocal": None, "link": None, "buy": None,
                               "qualifications": [], "tags": [], "resources": []})
    return sg

def resolve_listing_image(v):
    if not v: return None
    s = str(v).strip()
    if not s: return None
    if re.match(r'^(https?:|data:|//|assets/|\./)', s): return s
    return resolve_image(s)   # bare filename -> Azure board host (fallback)

listings = []
for row in lrows:
    if not row.get("Name"): continue
    if str(row.get("Include") or "yes").lower() == "no": continue
    name = str(row.get("Name")).strip()
    refs = [resolve_ref(r, name) for r in split(row.get("Boards"))]
    listings.append({
        "name": name, "repo": (str(row.get("Repo")).strip() or None) if row.get("Repo") else None,
        "category": str(row.get("Type") or "uncategorized").strip().lower(),
        "status": str(row.get("Status") or DEFAULT_STATUS).strip().lower(),
        "languages": split(row.get("Languages")),
        "features": sorted({TOPIC_NORM.get(t.lower(), t.lower()) for t in split(row.get("Topics"))} - DROP_TOPICS),
        "boards": refs, "description": str(row.get("Description") or "").strip(),
        "url": (str(row.get("Link")).strip() or None) if row.get("Link") else None,
        "image": resolve_listing_image(row.get("Image")),
    })

# ---------- live GitHub facts ----------
def gh_get(path):
    req = urllib.request.Request("https://api.github.com" + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "iotc-index",
                 **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)

facts = {}; org_repos = []
try:
    page = 1
    while True:
        batch = gh_get(f"/orgs/{ORG}/repos?per_page=100&page={page}&type=public&sort=updated")
        org_repos += batch
        if len(batch) < 100: break
        page += 1
    for r in org_repos:
        facts[r["name"]] = {"description": r.get("description") or "",
                            "languages": [r["language"]] if r.get("language") else [],
                            "stars": r.get("stargazers_count", 0), "updated": r.get("updated_at"),
                            "archived": r.get("archived")}
except Exception as e:
    print(f"[info] GitHub facts unavailable ({e}); using workbook data only.", file=sys.stderr)

# ---------- assemble index ----------
def board_ref(sg):
    b = board_defs[sg]
    o = {"slug": sg, "vendor": b["vendor"], "name": b["name"]}
    integ = b.get("integrator", b["vendor"])
    if integ and integ != b["vendor"]: o["integrator"] = integ
    if b.get("partNumber"): o["partNumber"] = b["partNumber"]
    if b.get("image"): o["image"] = b["image"]
    if b.get("imageLocal"): o["imageLocal"] = b["imageLocal"]
    return o

out = []; used_repos = set()
for L in listings:
    live = facts.get(L["repo"]) if L["repo"] else None
    if L["repo"]: used_repos.add(L["repo"])
    boards = [board_ref(s) for s in L["boards"]]
    base = {"repo": L["repo"],
            "url": L["url"] or (f'https://github.com/{ORG}/{L["repo"]}' if L["repo"] else None),
            "displayName": L["name"], "description": L["description"] or (live or {}).get("description", ""),
            "category": L["category"], "status": L["status"],
            "languages": L["languages"] or (live or {}).get("languages", []),
            "features": L["features"], "stars": (live or {}).get("stars", 0),
            "updated": (live or {}).get("updated", "2026-06-01T00:00:00Z"),
            "image": L["image"],
            "described": bool(L["description"] or L["repo"]), "hidden": False}
    if L["category"] == "sample" and len(boards) > 1:
        for b in boards:
            out.append({**base, "id": f'{slug(L["name"])}::{b["slug"]}', "boards": [b],
                        "board": b, "manufacturers": [b["vendor"]]})
    else:
        out.append({**base, "id": slug(L["name"]), "boards": boards,
                    "board": boards[0] if boards else None,
                    "manufacturers": sorted({b["vendor"] for b in boards}) if boards else []})

vis = [r for r in out if not r["hidden"]]
mfrs = sorted({m for r in vis for m in r["manufacturers"] if m and m != "Other"})
used_slugs = {b["slug"] for r in vis for b in r["boards"]}

# how many listings target each board
board_listings = {}
for r in vis:
    for b in r["boards"]:
        board_listings[b["slug"]] = board_listings.get(b["slug"], 0) + 1

# full board registry: every catalogued board (used + orphan), with resources/buy/detail.
# Skip "dead-end" virtual boards (no image, no buy, no resources, no product link) so the
# gallery never shows a fully blank card; listing references to them still resolve.
def dead_end(b):
    return not (b.get("image") or b.get("imageLocal") or b.get("buy") or b.get("link") or b.get("resources"))
busd = []
for sg in sorted([s for s in board_defs if not s.startswith("x-")],
                 key=lambda s: board_defs[s]["name"].lower()):
    b = board_defs[sg]
    if dead_end(b):
        continue
    rec = {k: b[k] for k in ["slug","vendor","name","partNumber","image","imageLocal",
                             "link","buy","qualifications","tags","resources"]}
    rec["integrator"] = b.get("integrator", b["vendor"])
    rec["listings"] = board_listings.get(sg, 0)
    busd.append(rec)

# topic facet (frequency) — features are already cleaned of DROP_TOPICS upstream
CAP = set()
tagcount = {}
for r in vis:
    for t in r["features"]:
        if t.lower() in CAP: continue
        tagcount[t] = tagcount.get(t, 0) + 1
topics = [{"tag": t, "count": c} for t, c in
          sorted(tagcount.items(), key=lambda kv: (-kv[1], kv[0]))]

# partner showcase metadata
boardcount = {}; listingcount = {}
for b in busd: boardcount[b["vendor"]] = boardcount.get(b["vendor"], 0) + 1
for r in vis:
    for m in r["manufacturers"]: listingcount[m] = listingcount.get(m, 0) + 1
partners = []
for m in sorted(set(list(boardcount) + list(listingcount))):
    if m == "Other": continue
    info = next((x["url"] for x in res_by_mfr.get(m, []) if x["kind"] == "info"), None)
    partners.append({"name": m, "slug": slug(m),
                     "logo": (BRAND_BASE + PARTNER_LOGO[m]) if m in PARTNER_LOGO else None,
                     "info": info, "boards": boardcount.get(m, 0), "listings": listingcount.get(m, 0)})

n_guides = sum(len([x for x in b["resources"] if x["kind"] in ("quickstart","developer")]) for b in busd)
n_demos  = sum(len([x for x in b["resources"] if x["kind"] == "demo"]) for b in busd)

index = {
    "org": ORG, "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "pagesUrl": PAGES_URL, "imageBase": IMAGE_BASE, "imageLocalBase": IMAGE_LOCAL, "brandBase": BRAND_BASE,
    "partners": partners,
    "facets": {"manufacturers": mfrs, "topics": topics, "boards": busd},
    "counts": {"total": len(vis), "manufacturers": len(mfrs), "boards": len(busd),
               "sdks": sum(1 for r in vis if r["category"] in ("sdk","library")),
               "examples": sum(1 for r in vis if r["category"] == "sample"),
               "guides": n_guides, "demos": n_demos,
               "partners": sum(1 for p in partners if p["logo"])},
    "repos": out,
}
def write_stable(path, new_text, ts_re):
    """Write new_text, but if the only difference from the existing file is the
    timestamp (matched by ts_re), leave the file untouched. Keeps generated
    artifacts byte-identical when nothing real changed, so CI commits nothing."""
    if os.path.exists(path):
        old = open(path, encoding="utf-8").read()
        if re.sub(ts_re, "TS", old) == re.sub(ts_re, "TS", new_text):
            return False
    open(path, "w", encoding="utf-8").write(new_text)
    return True

os.makedirs(OUT, exist_ok=True)
index_text = json.dumps(index, indent=2, ensure_ascii=False)
changed_index = write_stable(os.path.join(OUT, "index.json"), index_text, r'"generated": "[^"]*"')

# ---------- AUDIT ----------
orphan = [d for s, d in board_defs.items() if not s.startswith("x-") and s not in used_slugs]
no_image = [d for s, d in board_defs.items()
            if not s.startswith("x-") and not d.get("image") and not d.get("imageLocal")]
uncatalogued = [r for r in org_repos if not r.get("archived") and r["name"] not in used_repos] if org_repos else []
incomplete = [L["name"] for L in listings
              if (L["category"] == "sample" and not L["features"]) or (not L["description"] and not L["repo"])]

A = ["# /IOTCONNECT Index — Audit Report", "",
     f"_Generated {index['generated']}_  ·  {len(vis)} listings · {len(busd)} boards "
     f"({len(used_slugs)} in use) · {len(mfrs)} manufacturers · {len(res_rows)} resources", "",
     "## ⚠ Boards referenced but missing from the Boards sheet"]
if missing_boards:
    for ref, who in sorted(missing_boards.items()):
        A.append(f"- **{ref}** — referenced by: {', '.join(sorted(who))}")
else:
    A.append("- none — every referenced board is defined.")
A += ["", "## Boards with no image (Azure or local)"]
A += [f"- {d['vendor']} · {d['name']} ({d.get('partNumber') or 'no PN'})" for d in no_image] or ["- none."]
A += ["", "## Boards not used by any listing (orphans)"]
A += [f"- {d['vendor']} · {d['name']} ({d.get('partNumber') or 'no PN'})" for d in orphan] or ["- none."]
A += ["", "## Org repos with no listing (candidates to add)"]
if org_repos:
    A += [f"- {r['name']} — {r.get('description') or 'no description'}" for r in uncatalogued] or ["- none — every public repo has a listing."]
else:
    A.append("- (run with GITHUB_TOKEN to detect uncatalogued repos)")
A += ["", "## Listings missing description or topics"]
A += [f"- {n}" for n in incomplete] or ["- none."]
changed_audit = write_stable(os.path.join(OUT, "AUDIT.md"), "\n".join(A) + "\n", r'_Generated \S+Z_')

print(f"index.json: {len(vis)} listings, {len(mfrs)} manufacturers, {len(busd)} boards, "
      f"{len(res_rows)} resources, {n_guides} guides, {n_demos} demos")
print(f"AUDIT: {len(missing_boards)} missing-board refs, {len(no_image)} no-image, {len(orphan)} orphan, "
      f"{len(uncatalogued)} uncatalogued repos, {len(incomplete)} incomplete listings")
print("changed: " + (", ".join(f for f, c in [("index.json", changed_index), ("AUDIT.md", changed_audit)] if c)
                     or "nothing (timestamp-only; no rewrite)"))
