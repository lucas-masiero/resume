# Lucas Masiero - Resume

`resume.json` is the sole editable CV, compatible with Resumy 0.3.0 / CV schema
v2. Person contains contacts; sidebar contains profile, languages, technical
skills, education and interests; main contains experience, projects and
**Authored Books**. Projects are Cohesian, HomeSolution and LeetCode.

Cohesian credits Lucas as founder, software engineer and author. Authored Books
introduces the Go textbook briefly and describes Bookly Up's first System
Architecture edition in more detail. The Modules Implementation and
Infrastructure editions are explicitly planned. Previous architecture-study
and historical-work sections have been removed from this CV.

## Generate

Python 3.11+, ReportLab and Pillow are required. The wrapper uses the local
Resumy checkout at `../../Cohesian/tools/resumy`, configured in
`front.config.json`; no npm or global editable installation is needed.

```sh
python3 scripts/resume.py check
python3 scripts/resume.py pdf
python3 scripts/resume.py front
python3 scripts/resume.py build
python3 -m unittest discover -s tests
```

`build` validates, generates `output/pdf/lucas-masiero-resume.pdf` and an exact
copy of its input as `output/pdf/lucas-masiero-resume.json`, then exports `front/`. The current CV has three A4 pages. `cfg.toml` owns its theme; the
portrait is in `assets/`. The output PDF, matching JSON snapshot and input
fingerprint are versioned in Git. Edit the root `resume.json`; the output JSON
is a generated snapshot, not a second editable CV.

`pdf` requires only CV inputs and Resumy. `front` also requires the configured
local project sources and a PDF built from the current JSON/theme/photo.
Input fingerprints prevent exporting a stale PDF; use `build` after edits.
The PDF engine remains Resumy; this script supplies orchestration/export only.

## Front contract and portfolio

`front.config.json` selects contacts and maps project entry indices to IDs and
sources. Each project role/context comes from its CV entry subtitle, not a
second config value. Cohesian metadata comes from `Cohesian/site/front/` and its prepared
catalogs. HomeSolution/LeetCode contributions are authored here, with repo links.
The export converts inline formatting into primitive text and named links.

`front/manifest.json` contains person, profile, education, technical skills,
languages, experience, projects and authored books. `pdf` points to
`assets/resume.pdf`. It includes the portrait, the current CV, its schema and
Cohesian's visual bundle with source/license notices. Book PDFs are linked to
the publication owner; they are not copied. The PDF checksum and source
fingerprints allow downstream validation. Do not hand-edit generated fronts.

Contacts selected for structured display are separate from the PDF's contacts.
Initially the structured contact list includes email, website and LinkedIn;
add `phone` to select it. The CV PDF retains the full authored contact block.

Portfolio's `npm run sync:front` now consumes this export plus Site's general
Cohesian presentation. It imports professional fields and the CV, keeps layout
choices local, and builds from its cached snapshots. Updating this JSON alone
does not refresh the portfolio: run this build, then portfolio sync/build.
No import clones/pulls repositories or downloads data.

The historical PDF and earlier JSON were references, not assertions that every
field was current. Source decisions and retained dates are documented in
`SOURCE.md`; newer user instructions and verified local project work govern.
See [workspace architecture](../../ARCHITECTURE.md) for the complete flow.
