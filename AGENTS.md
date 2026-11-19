# Personal resume workspace

- `resume.json` is the sole authored CV input, using Resumy CV schema v2.
  Validate with `python3 scripts/resume.py check`; use `python3 scripts/resume.py build` for PDF and front outputs.
- The supplied older PDF is a reference. Current user instructions and verified
  local project work take precedence. Keep employment, education, proficiency
  and outcomes grounded; do not infer current dates or new qualifications.
- General Cohesian metadata belongs to `../../Cohesian/site/front/`; personal
  roles/contributions belong here. Credit tools/books to Lucas within Cohesian.
- LeetCode is personal algorithm practice; do not claim a score, solved count,
  ranking, contest result or activity streak without evidence.
- `front.config.json` selects public contacts and project references. `front/`
  is generated; edit its inputs instead. Exports perform no Git/network actions.
- Commit the PDF and its exact `lucas-masiero-resume.json` input snapshot under
  `output/pdf/`, together with the input fingerprint. Keep source JSON, assets, provenance and
  schemas separate from the independently versioned Resumy implementation.
- Do not modify Resumy or global installations incidentally. Use its configured
  local source checkout. Portfolio consumes this export through its explicit sync step.
- Commits, pushes, publishing, visibility changes and deployments require the
  corresponding user instruction. Sign requested commits with `-S`.

- The active CV sections are experience, projects and Authored Books; retain
  the user-requested removal of architecture-study and historical-work sections.
- Go book coverage stays brief; Bookly Up first edition is architecture, with
  second (Modules Implementation) and third (Infrastructure) editions planned.
- Front exports its current CV PDF with a checksum; refresh the PDF after CV,
  theme or photo changes. Portfolio imports selected fields and that PDF.
