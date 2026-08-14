# data/ — the catalog source (CSV)

These four CSVs are the **single source of truth** for the site. Edit them, commit,
and the GitHub Action rebuilds `index.json` + `AUDIT.md`. GitHub renders each file
as a table and shows **row/cell-level diffs** in commits and PRs.

> Edit with **LibreOffice Calc**, **Google Sheets**, or **VS Code** (the *Edit CSV* /
> *Rainbow CSV* extensions give a grid view). Avoid Excel — it likes to reformat part
> numbers and re-quote fields. Save as UTF-8 CSV.

## `listings.csv` — the SDK / demo cards
| Column | Meaning |
|---|---|
| `Name` | Card title. |
| `Type` | `sample`, `sdk`, or `library`. A `sample` with several boards expands to one card per board; an `sdk`/`library` stays one card. |
| `Status` | `stable`, `beta`, `experimental`, `maintenance`, `deprecated`. Blank → Config `DEFAULT_STATUS`. |
| `Repo` | GitHub repo name in the org (drives live stars / last-updated). |
| `Languages` | Comma-separated. |
| `Topics` | Comma-separated filter tags (`ai`, `vision`, `lora`, …). |
| `Boards` | One or more board **Part Numbers** (must exist in `boards.csv`). Leave blank for platform-agnostic SDKs. |
| `Description` | Card text. |
| `Link` | Explicit URL (else derived from `Repo`). |
| `Include` | `no` hides the row. |
| `Image` | Picture for **board-less** rows: a tech logo (`assets/tech/python.svg`), a photo (`assets/listings/drone.png`), or a URL. Ignored when `Boards` is set (the board image is used).
| `Dashboards` | Pipe-separated /IOTCONNECT dashboard screenshot URLs. The first one leads the card tile. |
| `Photos` | Pipe-separated demo-in-action photo URLs (lead when no Dashboards). |
| `Overlay` | Optional small badge image shown in the tile's top-right corner (partner logo, sensor, award…). | |

## `boards.csv` — the hardware registry
`Manufacturer`, `Board Name`, `Part Number` (the key listings reference), `Image File`
(filename at Config `IMAGE_BASE`, or a full URL), `Image Local` (offline fallback under
`assets/boards/`), `Product Link`, `AWS Qualified` (`yes`/`no`), `Greengrass` (`yes`/`no`),
`Tags`, `Include`.

## `resources.csv` — per-board guides, demos & links
Powers the board detail drawer. `Ref` (a board **Part Number**, or a manufacturer name),
`RefType` (`board` / `manufacturer`), `Kind` (`buy` · `quickstart` · `developer` · `demo`
· `webinar` · `video` · `blog` · `doc` · `info`), `Title`, `URL`. The first `buy` row for a
board becomes its **Buy on Avnet** button.

## `config.csv` — key/value settings
`ORG`, `IMAGE_BASE`, `IMAGE_LOCAL_BASE`, `BRAND_BASE`, `DEFAULT_STATUS`, `PAGES_URL`.

---

Build locally: `python build_site.py` (Python 3, **no third-party deps**).
The pre-CSV Excel workbook is archived in [`../migration/`](../migration/).
