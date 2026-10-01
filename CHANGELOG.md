# Changelog

All notable changes to **AI Resume Analyzer** are documented here.

The format follows [Keep a Changelog][kac], and this project uses
[Semantic Versioning][semver].

> This log describes what the application actually does. Entries are never
> written for features that have not shipped.

[kac]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html

---

## [Unreleased]

### Added

- [Dockerfile](Dockerfile) production image that installs Tesseract OCR
  with its English language data (`tesseract-ocr`, `tesseract-ocr-eng`),
  verifies the OCR install at build time and runs the app under Gunicorn
  bound to Render's `$PORT`.
- [.dockerignore](.dockerignore) keeps `.env`, virtual environments and
  local uploads out of the image.
- Optional `TESSERACT_CMD` override plus an `ocr_status()` startup log for
  non-standard Tesseract locations.
- [docs/deployment.md](docs/deployment.md) with local Docker checks and
  safe Render switch-over steps.
- Per-stage timing logs for `/analyze` (`analyze.start`,
  `stage=… ms=… …`, `analyze.done status=200 total_ms=…`) and an
  `OCR summary` line (pages, characters, milliseconds, cap/target flags),
  so the Render logs show exactly where an analysis spends its time.
  Only durations, counts and internal ids are logged — original
  filenames, resume contents, e-mail addresses and secrets never are.
  Unexpected failures additionally log the stage they failed in with a
  full traceback.

### Fixed

- Mobile resume uploads no longer fail with "Unable to analyze this resume
  right now." on a deployment without the Tesseract OCR binary: an
  image-only/scanned PDF now yields a specific, actionable message, and any
  other extraction failure is reported the same way.
- Uploads whose filename sanitises to a non-Latin stem (for example
  `ரெஸ்யூம்.pdf`, which `secure_filename()` reduced to `pdf`) are accepted
  again — the extension is validated against the browser's raw filename.
- Corrupt, empty or password-protected PDF/DOCX downloads now get a
  "could not read this file" message instead of a generic error, and a
  locked temporary upload can no longer turn a handled error into an
  HTTP 500.
- Analysis failures log the stored object, size and exception type —
  never resume contents, passwords or secrets.
- The analyze page no longer sits forever on a disabled "Analyzing your
  resume..." button when the POST response is slow or never arrives (Render
  cold start, OCR of a large scan, dropped mobile connection, proxy
  timeout): a staged watchdog shows a "still analyzing" notice after 20 s
  and hands the button back with a retry message after 75 s, while a
  `pageshow` reset clears the stuck state after back/forward navigation.
- OCR — the only `/analyze` stage with no natural bound — is now capped:
  at most `MAX_OCR_PAGES` pages (default 8), stopping early once
  `OCR_TARGET_CHARS` (default 4000) characters are recognised, with page
  rasters limited to `OCR_MAX_PAGE_DIMENSION` pixels (default 2400). A
  large scanned upload could otherwise keep the request open past the
  75 s watchdog on a small production instance, at which point the browser's
  retry aborted the still-pending request and the completed server response
  (logged as `POST /analyze … 200`) was discarded — the user stayed stuck
  on the Analyze page even though the analysis had succeeded. All three
  limits are environment-overridable.
- `/analyze` no longer spends OCR time on pages that do not need it. The
  PDF is read and parsed once per request (the embedded-text pass and the
  OCR loop share the same open document), a page whose embedded text
  layer is usable keeps that text and is never rasterised, and a
  perfectly uniform (blank) page never starts Tesseract. Pages that do
  need OCR are rasterised exactly once and handed to PIL straight from
  the pixmap samples — the per-page PNG encode/decode round trip is
  gone — and the loop stops immediately once `OCR_TARGET_CHARS`
  characters (embedded plus recognised) have been collected. Each OCR'd
  page now logs `OCR page=… ms=… zoom=… chars=…`, and the `OCR summary`
  line reports `text_pages=` and `blank_pages=` next to the existing
  counters. A mixed (part text, part scan) or partly blank upload
  previously sent every page to Tesseract. Scores, career match,
  skills, roadmap, recommendations and history behaviour are unchanged.
- The 75 s retry notice now says a new attempt starts the analysis over,
  so users can choose to keep waiting for a response that may already be
  on its way instead of cancelling it.

---

## [1.0.0] — Initial Release

The first complete, working release: a Flask + MySQL resume analysis and
career-planning platform.

### Added

**Accounts & authentication**

- Registration restricted to Gmail addresses.
- Six-digit OTP issued on registration, hashed before storage in
  `otp_tokens`.
- OTP lifecycle controls: 90-second expiry, 30-second resend cooldown,
  five-attempt limit, single-use consumption.
- Standalone `create_password` step after email verification.
- Forgot-password and reset-password flow reusing the same OTP machinery with
  a separate `reset` purpose.
- Salted password hashing via `werkzeug.security` — no plaintext storage.
- Session login, logout, and a profile page for account maintenance.
- `@login_required` guarding every analysis, history, and profile route.

**Resume ingestion**

- Upload of `.pdf` and `.docx`, capped at 10 MB.
- PDF text extraction through PyMuPDF.
- Automatic Tesseract OCR fallback for scanned PDFs when fewer than 50
  characters of embedded text are found.
- DOCX extraction covering both paragraphs and tables.
- Hardened storage: `secure_filename()` plus a random UUID filename.

**Analysis engine (deterministic NLP)**

- Skill detection over a catalog of 40 career profiles, with alias resolution
  (`SKILL_ALIASES`) and word-boundary regex matching.
- Section parsing for education, projects, experience, and certifications.
- Weighted resume score out of 100 — skills (30), education (20), projects
  (20), experience (20), certifications (10).
- Career match percentage computed from matched versus required skills.
- Matched-skill and missing-skill (skill-gap) breakdowns.
- High / Medium / Low learning priority assigned to each missing skill.
- Learning topics for 42 distinct skills.
- Staged learning roadmaps for 40 career paths.
- Recommended portfolio projects for 40 career paths.

**Machine learning**

- Auxiliary career recommender: `TfidfVectorizer` + `LogisticRegression`,
  persisted with `joblib`.
- Confidence score derived from `predict_proba`.
- Graceful degradation — if the model artifacts are missing or fail to load,
  the app logs a warning and continues serving the rule-based analysis.
- Retraining script (`ml_training/train_model.py`) and a small synthetic
  starter dataset.

**History and results**

- Every analysis persisted to `resume_analysis`.
- History page for comparing career matches across runs.
- Individual analysis detail view.
- Clear-history action scoped to the signed-in user.
- Per-result score breakdown.

**Infrastructure**

- MySQL schema (`database.sql`): `users`, `otp_tokens`, `resumes`,
  `resume_analysis` with foreign keys and lookup indexes.
- Configuration entirely through environment variables.
- Tailored `413`, `404`, and `500` error pages.
- Responsive templates and a shared navigation base layout.

### Notes

- The bundled model is trained on a 9-row synthetic dataset covering 3 careers
  and is intended as a starting point, not a production classifier. See
  [`docs/ml-pipeline.md`](docs/ml-pipeline.md).
- No automated test suite ships with this release; CI performs structural and
  import verification only.

---

## [Unreleased]

Nothing yet. Planned work is tracked in [GitHub Issues][issues].

[issues]: https://github.com/abinesh-0/ai-resume-/issues
