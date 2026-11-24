# Lucas Masiero — Resume

resume.json is the sole authored CV input, using Resumy CV schema v2. It
contains personal data, education/skills, work experience, projects and
Authored Books. Keep personal facts and implemented/planned work grounded.

## Validate and build

Python 3.11+, ReportLab and Pillow are required. build.config.json selects
the local Resumy source checkout. No Node.js or presentation framework is used.

```sh
python3 scripts/resume.py check
python3 scripts/resume.py build
python3 scripts/resume.py pdf
python3 -m unittest discover -s tests
```

build validates the native CV and reuses an already current PDF/JSON pair.
It regenerates when inputs changed; pdf explicitly renders again. cfg.toml
owns formatting and assets/ owns the portrait. No other project metadata or
source checkout, except the configured PDF engine, is read during generation.

Versioned outputs:

- output/pdf/lucas-masiero-resume.pdf
- output/pdf/lucas-masiero-resume.json — exact JSON input to that PDF
- output/pdf/resume-source.json — hashes of the JSON, theme and portrait

Edit the root resume.json; the named output JSON is a generated input snapshot.
The schema under schemas/ describes Resumy's intrinsic CV format. This repo
owns only its native CV sources and artifacts, not a rendering/export contract
for any website. Do not introduce presentation adapters or catalogs here.

The CV keeps Go book coverage brief and describes Bookly Up's architecture
edition in detail. Modules Implementation and Infrastructure remain planned.
See SOURCE.md for the historical source and retained factual limits.
