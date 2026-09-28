# Changelog

All notable changes to **AI Resume Analyzer** are documented here.

The format follows [Keep a Changelog][kac], and this project uses
[Semantic Versioning][semver].

> This log describes what the application actually does. Entries are never
> written for features that have not shipped.

[kac]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html

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
