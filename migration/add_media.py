#!/usr/bin/env python3
"""add_media.py — pull demo dashboard screenshots + hardware photos into listings.

Source: ../../iotc-master-catalog.xlsx (sheet "Demos"). Each demo row carries up to
6 "Dashboard N" image URLs (the /IOTCONNECT cloud dashboard) and 5 "Demo Image N"
URLs (real hardware-in-action photos). We match each demo to a listing row in
data/listings.csv (by normalised name, then by GitHub repo) and fill two new columns:

  Dashboards  pipe-separated dashboard screenshot URLs
  Photos      pipe-separated demo/hardware photo URLs

These power the dashboard-first card thumbnail and the sample detail drawer gallery.
Re-runnable: it rewrites both columns from the workbook each time.
"""
import os, re, csv
from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
XLSX = os.path.join(os.path.dirname(ROOT), "iotc-master-catalog.xlsx")
LISTINGS = os.path.join(ROOT, "data", "listings.csv")
SEP = " | "

def norm(s): return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()
def ghkey(s):
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", str(s or ""), re.I)
    return (m.group(1).lower() + "/" + m.group(2).lower()) if m else None

# demo name -> listing name, for the few that don't match by name or repo
ALIAS = {
    "edge ai solutions featuring jetson": "nvidia jetson",  # best-effort; skipped if absent
}

# ---- read listings ----
rows = list(csv.reader(open(LISTINGS, newline="", encoding="utf-8")))
H = rows[0]
for col in ("Dashboards", "Photos"):
    if col not in H:
        H.append(col)
idx = {c: H.index(c) for c in H}
data = rows[1:]
for r in data:                                   # pad rows to new width
    while len(r) < len(H): r.append("")

by_name, by_gh = {}, {}
for r in data:
    by_name.setdefault(norm(r[idx["Name"]]), r)
    gh = ghkey(r[idx["Link"]]) or (("avnet-iotconnect/" + r[idx["Repo"]].lower()) if r[idx["Repo"]] else None)
    if gh: by_gh.setdefault(gh, r)

# ---- read demos ----
wb = load_workbook(XLSX, data_only=True)
ws = wb["Demos"]
hdr = [c.value for c in ws[1]]
demos = [{hdr[i]: (str(rw[i]).strip() if rw[i] is not None else "")
          for i in range(len(hdr)) if hdr[i]}
         for rw in ws.iter_rows(min_row=2, values_only=True) if any(rw)]

# accumulate per listing row (dedup, order-preserving)
dash_by_row, photo_by_row = {}, {}
matched = unmatched = 0
for d in demos:
    dashes = [d.get(f"Dashboard {i}", "") for i in range(1, 7)]
    photos = [d.get(f"Demo Image {i}", "") for i in range(1, 6)]
    dashes = [u for u in dashes if u.startswith("http")]
    photos = [u for u in photos if u.startswith("http")]
    if not (dashes or photos):
        continue
    nm = norm(d.get("Demo"))
    row = by_name.get(nm) or by_name.get(norm(ALIAS.get(nm, ""))) or by_gh.get(ghkey(d.get("Github Link")))
    if not row:
        unmatched += 1
        print(f"  [unmatched] {d.get('Manufacturer')} | {d.get('Demo')}  ({len(dashes)+len(photos)} imgs)")
        continue
    matched += 1
    rid = id(row)
    for u in dashes:
        dash_by_row.setdefault(rid, [])
        if u not in dash_by_row[rid]: dash_by_row[rid].append(u)
    for u in photos:
        photo_by_row.setdefault(rid, [])
        if u not in photo_by_row[rid]: photo_by_row[rid].append(u)

# ---- write back ----
filled = 0
for r in data:
    rid = id(r)
    r[idx["Dashboards"]] = SEP.join(dash_by_row.get(rid, []))
    r[idx["Photos"]] = SEP.join(photo_by_row.get(rid, []))
    if dash_by_row.get(rid) or photo_by_row.get(rid): filled += 1

csv.writer(open(LISTINGS, "w", newline="", encoding="utf-8"), lineterminator="\n").writerows([H] + data)
print(f"matched {matched} demos -> {filled} listings; {unmatched} unmatched. "
      f"columns: Dashboards, Photos")
