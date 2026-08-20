# Catalog contributor guide (for Claude sessions)

How to add or update entries in the **/IOTCONNECT Enablement Hub** catalog from any
session — including sessions working in *other* project directories (a demo repo, an
SDK, a board bring-up). The catalog lives in this repo; the site is generated from
the CSVs in [`data/`](data/).

**Reference this file from another project:** `Read c:\dev\website\iotc-index\CLAUDE.md`

- Live site: https://avnet-iotconnect.github.io/iotc-index/
- Column-by-column schema: [`data/README.md`](data/README.md) — read it alongside this guide.
- Architecture / data flow: [`README.md`](README.md)

## Ground rules

- **Path (this machine):** `c:\dev\website\iotc-index`
- **Remotes:** `avnet` = `avnet-iotconnect/iotc-index` (**production — push here, branch `main`**).
  `origin` = `mlamp99/iotc-index` (**archived staging — never push**).
- **Commits:** plain messages, **no** `Co-Authored-By: Claude` / "Generated with Claude Code" trailers.
- **Sync first, always:** other sessions and CI also commit to `main`.
  `git fetch avnet && git merge --ff-only avnet/main`. If it won't fast-forward, rebase your
  CSV edits on top of `avnet/main` — never force-push, never clobber production edits.
- `index.json` and `AUDIT.md` are **generated** — never hand-edit. CI rebuilds them on every
  commit touching `data/`, so committing only CSV/asset changes is fine.
- A repo only appears in audit tracking if it is **public in the `avnet-iotconnect` org**.

## What goes where

| You have… | Do this |
|---|---|
| A new demo/SDK/tool repo | Add row(s) to `data/listings.csv` |
| A repo with several use-case demos | **One row per use-case**, not one per repo. Name `"<Thing> — <Use case>"` (em-dash), `Link` → the demo subfolder, per-row Topics. Precedent: SAMA7D65 / PolarFire / Zephyr rows |
| A demo verified on a new board | Append the Part Number to the row's `Boards` cell — a `sample` row expands to one card per board automatically |
| A board not yet in the catalog | The **completeness bundle** (below) |
| A per-board guide/video/purchase link | Add a `data/resources.csv` row |
| A new AI model used by a demo | Add it to `data/models.csv`, reference its id from the listing's `Models` |

## Editorial conventions (what the READMEs don't say)

- **Type:** `sample` | `sdk` | `library` | `tool` — nothing else (`demo` was purged; don't reintroduce it).
- **Topics:** lowercase-kebab, *distinctive capabilities only* (`edge-ai`, `vision`, `webrtc`,
  `zephyr`, `secure-element`, `clicks`, `vlm`…). **Never** `telemetry`, `commands`, `ota`, `twin`
  — every demo has those; the build drops them. Reuse existing tags before inventing one
  (`python -c "import csv;print(sorted({t.strip() for r in csv.DictReader(open('data/listings.csv',encoding='utf-8')) for t in r['Topics'].split(',') if t.strip()}))"`).
- **Boards on cards = hardware-verified only.** Builds-only or planned boards wait until verified.
  Boards with no direct IP link to /IOTCONNECT (UART-feeder patterns) stay off board cards.
- **Board-less rows need an `Image`** (tech logo `assets/tech/*.svg`, photo `assets/listings/*.png`, or URL).
  When `Boards` is set the board image is used and `Image` is ignored.
- **`Name` drives the card id and deep-links** (`#demo/<slug>`). Renaming breaks shared links — don't rename casually.
- **Descriptions:** 2–4 sentences, marketing-grade, say what it does and what's special
  (sealed keys, NPU, verified hardware). Match neighbors' tone.
- **Status:** blank → `beta`. Use `experimental` for phase-1/WIP entries; or hold the row until demo-ready.
- **Imagery:** `Dashboards` / `Photos` are pipe-`|`-separated URLs; first Dashboards image leads the tile.
  Verify every URL returns 200. GitHub-hosted images: use `raw.githubusercontent.com/...` (not `/blob/`) URLs.
  No good image? Leave blank — tile imagery is also curated later with the iotc-index-curator app.

## New-board completeness bundle

Adding a Part Number that listings reference means **all** of:
1. `data/boards.csv` row — Manufacturer, Board Name, Part Number, image (`Image Local` file in
   `assets/boards/` and/or `Image File` URL), Product Link, Tags, `Silicon` (chip vendor —
   drives partner grouping; integrator boards use `"Tria / NXP"`-style Manufacturer).
2. `data/resources.csv` rows — at minimum `buy` (Avnet/Newark shop URL — becomes the Buy button),
   `quickstart`, and `doc`.
3. A real board photo — official vendor page or Zephyr board docs are good sources; save to
   `assets/boards/<PART-NUMBER>.jpg` if hotlinking is unreliable.

## Workflow from another project session

```bash
cd c:/dev/website/iotc-index
git fetch avnet && git merge --ff-only avnet/main

# Append rows with python csv.writer (QUOTE_MINIMAL, UTF-8, lineterminator='\n').
# Prefer appending / surgical line edits over rewriting files (keeps diffs reviewable).

# Validate structure (fast, no build needed):
python - <<'PY'
import csv
def split(s): return [x.strip() for x in str(s or "").replace(";", ",").split(",") if x.strip()]
boards={v.strip().lower() for r in csv.DictReader(open('data/boards.csv',encoding='utf-8'))
        for v in (r['Part Number'], r['Board Name']) if v.strip()}
mids={r['Model'].strip() for r in csv.DictReader(open('data/models.csv',encoding='utf-8'))}
rows=list(csv.reader(open('data/listings.csv',encoding='utf-8')))
for r in rows:
    assert len(r)==len(rows[0]), (len(r), r[0])   # every row matches the header width
for r in csv.DictReader(open('data/listings.csv',encoding='utf-8')):
    bad =[b for b in split(r['Boards']) if b.lower() not in boards]
    badm=[m for m in split(r['Models']) if m not in mids]
    if bad:  print('MISSING BOARD:', r['Name'], bad)
    if badm: print('UNKNOWN MODEL:', r['Name'], badm)
print('ok')   # known pre-existing warning: MISSING BOARD 'uno' (Vision AI Demonstrator)
PY

# Optional full local build (needs token; takes 2-4 min — run in background):
GITHUB_TOKEN="$(gh auth token)" python build_site.py
# then check AUDIT.md: 0 uncatalogued repos, no NEW missing-board refs, 0 incomplete listings

git add data/ assets/            # + index.json AUDIT.md only if you built locally
git commit -m "Catalog <thing>"  # plain message, no Claude trailer
git push avnet main              # CI rebuilds index.json + AUDIT.md and deploys Pages
```

Verify after push: `gh run list --repo avnet-iotconnect/iotc-index --limit 2` — the
`build-index` run should go green, then the entry is live on the site.

## CSV hygiene

- UTF-8; em-dashes in names are fine and conventional. Keep files newline-terminated.
- Field counts must match the header row exactly (listings 15 · boards 11 · resources 5 · models 8).
- Multi-value cells: Topics/Languages/Boards/Models accept commas or semicolons (the build treats
  them the same); Dashboards/Photos are pipe-`|`-separated. Prefer commas for consistency.
- Don't edit with Excel (it mangles part numbers and quoting).
