#!/usr/bin/env python3
"""
add_demos.py — append the generated demo cards / boards / resources for the
multi-board repos (iotc-python-lite-sdk-demos, iotc-python-greengrass-demos,
meta-iotconnect-docs) into data/*.csv. Topics are derived to the user's taxonomy
(distinctive capabilities — kvs/webrtc/edge-ai/… — never telemetry/commands).
"""
import os, csv, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
gen = json.load(open(os.path.join(HERE, "_gen.json"), encoding="utf-8"))

def read(name):
    with open(os.path.join(DATA, f"{name}.csv"), newline="", encoding="utf-8") as f:
        r = csv.reader(f); rows = list(r)
    return rows[0], rows[1:]

def write(name, header, rows):
    with open(os.path.join(DATA, f"{name}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(header); w.writerows(rows)

# ---------- topic taxonomy (distinctive capabilities only) ----------
def topics_for(name, desc, link):
    t = f"{name} {desc} {link}".lower()
    out = []
    def add(*xs):
        for x in xs:
            if x not in out: out.append(x)
    if "webrtc" in t: add("kvs", "webrtc", "video")
    elif "kvs" in t or "kinesis" in t or "putmedia" in t: add("kvs", "video")
    if "face recog" in t or "face_recog" in t or "face recognition" in t: add("face-recognition")
    if any(k in t for k in ["driver monitoring", "/dms", "dms ", "dms-", "(dms)"]): add("vision", "edge-ai")
    if any(k in t for k in ["vision", "object detection", "image classif", "eiq", "camera", "ai inference", "pose", "segmentation"]): add("vision")
    if any(k in t for k in ["keyword spotting", "kws", "voice", "audio", "sound", "speech", "blackjack"]): add("audio")
    if "gesture" in t: add("gesture")
    if "anomaly" in t: add("anomaly-detection")
    if "file upload" in t or "file-upload" in t: add("file-upload")
    if "greengrass" in t: add("greengrass")
    if "robot" in t: add("robotics")
    if "polarfire" in t or "fpga" in t: add("fpga")
    if any(k in t for k in ["neural network", "nn-accelerator", "nn accelerator", "accelerator", "classifier", "inference", "machine learning", " ml ", "model"]): add("edge-ai", "ai")
    if "power monitor" in t or "pac1934" in t: add("sensors")
    if "system monitor" in t: add("sensors")
    if ("vision" in out or "audio" in out) and "edge-ai" not in out: add("edge-ai")
    out = [x for x in out if x not in ("telemetry", "commands", "ota", "twin")]
    return ", ".join(out) if out else "edge-ai"

# ---------- new boards (canonical readable PNs the listings already use) ----------
CANON = {"arduino": "ARDUINO-UNO-Q", "video kit": "MPFS-VIDEO-KIT", "jetson": "JETSON-ORIN",
         "rz/g3e": "RZ-G3E-EVK", "rz/v2h": "RZ-V2H-EVK", "mp215": "STM32MP215F-DK"}
def canon_pn(boardName):
    n = boardName.lower()
    for k, v in CANON.items():
        if k in n: return v
    return None

bH, bRows = read("boards")
existing_pn = {r[bH.index("Part Number")].strip().lower() for r in bRows}
added_boards = 0
for nb in gen["newBoards"]:
    pn = canon_pn(nb["boardName"])
    if not pn or pn.lower() in existing_pn: continue
    row = [""] * len(bH)
    row[bH.index("Manufacturer")] = nb["manufacturer"]
    row[bH.index("Board Name")]   = nb["boardName"]
    row[bH.index("Part Number")]  = pn
    row[bH.index("Product Link")] = nb.get("productLink", "")
    row[bH.index("AWS Qualified")] = nb.get("awsQualified", "no")
    row[bH.index("Greengrass")]   = nb.get("greengrass", "no")
    row[bH.index("Tags")]         = nb.get("tags", "")
    row[bH.index("Include")]      = "yes"
    bRows.append(row); existing_pn.add(pn.lower()); added_boards += 1
write("boards", bH, bRows)

# ---------- listings (drop superseded umbrella; append per-example cards) ----------
lH, lRows = read("listings")
i = {c: lH.index(c) for c in lH}
DROP = {"python lite sdk demos"}                      # umbrella now replaced by per-example cards
lRows = [r for r in lRows if r[i["Name"]].strip().lower() not in DROP]
existing_names = {r[i["Name"]].strip().lower() for r in lRows}
existing_links = {r[i["Link"]].strip() for r in lRows if r[i["Link"]].strip()}

def add_listings(items, repo):
    n = 0
    for it in items:
        name = re.sub(r"&amp;", "&", it["name"]).strip()
        if name.lower() in existing_names or it["link"].strip() in existing_links:
            continue
        row = [""] * len(lH)
        row[i["Name"]] = name
        row[i["Type"]] = "sample"
        row[i["Status"]] = "beta"
        row[i["Repo"]] = repo
        row[i["Languages"]] = "Python"
        row[i["Topics"]] = topics_for(name, it.get("description", ""), it["link"])
        row[i["Boards"]] = it["boards"].strip()
        row[i["Description"]] = re.sub(r"&amp;", "&", it.get("description", "")).strip()
        row[i["Link"]] = it["link"].strip()
        row[i["Include"]] = "yes"
        row[i["Image"]] = ""
        lRows.append(row); existing_names.add(name.lower()); existing_links.add(it["link"].strip()); n += 1
    return n

n_lite = add_listings(gen["liteListings"], "iotc-python-lite-sdk-demos")
n_gg = add_listings(gen["ggListings"], "iotc-python-greengrass-demos")
write("listings", lH, lRows)

# ---------- resources: quickstarts (from gen) + meta-iotconnect-docs ----------
rH, rRows = read("resources")
seen = {(r[0].strip().lower(), r[2].strip().lower(), r[4].strip()) for r in rRows}
def add_res(ref, kind, title, url):
    key = (ref.strip().lower(), kind.strip().lower(), url.strip())
    if key in seen or not url.strip(): return 0
    rRows.append([ref, "board", kind, title, url]); seen.add(key); return 1

n_res = 0
for r in gen["resources"]:
    n_res += add_res(r["ref"], "quickstart", r["title"], r["url"])

META = "https://github.com/avnet-iotconnect/meta-iotconnect-docs/tree/main/"
META_RES = [
    ("MSC SM2S-IMX8PLUS", "developer", "Yocto Build Guide (mickledore)", META + "Build/MSC-SM2S-IMX8Plus/mickledore"),
    ("AES-MC-SBC-IMX8M-G", "developer", "Yocto Build Guide (kirkstone)", META + "Build/MaaXBoard/kirkstone"),
    ("AES-RZB-V2L-SK-G", "developer", "Yocto Build Guide (dunfell)", META + "Build/RZBoardV2L/dunfell"),
    ("AES-RZB-V2L-SK-G", "demo", "AI Camera Demo (Yocto)", META + "QuickStart/Renesas/RZBoard-V2L/demo-iotc-ai-camera"),
    ("RPI5-4GB-SINGLE", "developer", "Yocto Build Guide", META + "Build/RaspberryPi"),
    ("ATSAMA5D27-SOM1-EK1", "developer", "Yocto Build Guide (kirkstone)", META + "Build/SAMA5D2/kirkstone"),
    ("STM32MP157F-DK2", "developer", "Yocto Build Guide (STM32MP1)", META + "Build/STM32MP1"),
    ("STM32MP135F-DK", "developer", "Yocto Build Guide (STM32MP1)", META + "Build/STM32MP1"),
    ("STM32MP257F-EV1", "developer", "Yocto Build Guide (mickledore)", META + "Build/STM32MP257-EV1/mickledore"),
    ("STM32MP257F-DK", "demo", "X-LINUX-AI Vision Demo (Yocto)", META + "QuickStart/ST/STM32MP257/demo-iotc-x-linux-ai"),
]
n_meta = sum(add_res(*m) for m in META_RES)
write("resources", rH, rRows)

print(f"boards +{added_boards} | listings +{n_lite} lite +{n_gg} greengrass | resources +{n_res} quickstart +{n_meta} meta")
