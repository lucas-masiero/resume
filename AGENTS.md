# Personal resume workspace

resume.json is the sole authored CV, using native Resumy CV schema v2.
Read README.md and SOURCE.md. Validate with python3 scripts/resume.py check;
build with python3 scripts/resume.py build. build.config.json selects Resumy.

- Own personal data, education/skills, experience, projects and Authored Books.
  Preserve grounded employment/education facts and planned/implemented limits.
- LeetCode is personal algorithm practice; never invent rankings or counts.
- Keep Go book coverage brief and Bookly Up architecture more detailed. Its
  implementation and infrastructure editions remain planned.
- This repo is agnostic of external consumers. Keep native CV JSON, photo,
  theme and PDF/JSON output pair; do not add presentation exports, website
  schemas, catalog dependencies or consumer field selections.
- Keep the PDF and identically named JSON under output/pdf/ versioned along
  with the input fingerprint. Never hand-edit generated output JSON.
- Reuse an already current artifact to avoid metadata-only PDF churn. The
  explicit pdf command regenerates; build refreshes after source changes.
- Do not modify Resumy or global installations incidentally. Test with
  python3 -m unittest discover -s tests. Sign authorized commits with -S.
- Pushes, visibility, publication and deployment require user authorization.
