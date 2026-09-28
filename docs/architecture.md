# Architecture

Technical reference for AI Resume Analyzer. Everything here is read directly
from `app.py`, `database.sql`, and `templates/` — no aspirational components.

> **Structural honesty note:** this is a **monolith**. `app.py` is a single
> ~5,000-line Flask module holding configuration, data catalogues, the analysis
> engine, OTP/email logic, database access, and 17 routes. There is no
> blueprint split, service layer, ORM, cache, queue, or API gateway. Diagrams
> below show logical responsibilities, not separate deployable services.

---

## System overview

```mermaid
flowchart TD
    U([User browser])

    subgraph FLASK["Flask monolith — app.py"]
        direction TB
        ROUTES["Routes &amp; views<br/>17 endpoints"]
        GUARD["login_required<br/>session guard"]
        AUTH["OTP + password flow<br/>secrets · werkzeug.security"]
        MAIL["Flask-Mail<br/>SMTP :587 STARTTLS"]
        UP["Upload handler<br/>secure_filename + UUID"]
        EXTRACT["Text extraction<br/>PyMuPDF · python-docx · Tesseract"]
        NLP["Analysis engine<br/>regex skills · section parse · scoring"]
        ML["Auxiliary ML model<br/>TF-IDF + Logistic Regression"]
        CTX["Result context builder"]
    end

    FS[("uploads/<br/>disk storage")]
    PKL[("models/*.pkl<br/>joblib artefacts")]
    DB[("MySQL<br/>users · otp_tokens<br/>resumes · resume_analysis")]
    SMTP[[Gmail SMTP]]

    U -->|HTML forms| ROUTES
    ROUTES --> GUARD
    ROUTES --> AUTH
    AUTH --> MAIL --> SMTP
    AUTH --> DB
    ROUTES --> UP --> FS
    UP --> EXTRACT
    EXTRACT -->|plain text| NLP
    NLP <-->|optional predict| ML
    PKL -.->|loaded at import, optional| ML
    NLP --> CTX
    NLP --> DB
    CTX -->|render_template| U
```

*Solid = always on this path · dashed = optional, degrades gracefully.*

---

## What runs at process start

Before the first request, importing `app.py`:

1. `load_dotenv()` reads `.env` if present — **absence is fine**, every lookup
   has a default.
2. Flask app created; `SECRET_KEY`, `MAX_CONTENT_LENGTH` (10 MB), and OTP
   timings set from environment.
3. `Mail(app)` initialised.
4. Static catalogues built in memory: `CAREERS` (40), `SKILLS` (167),
   `SKILL_ALIASES` (10), `LEARNING_TOPICS` (42), `CAREER_ROADMAPS` (40),
   `PROJECTS` (40).
5. `joblib.load()` attempts the two model artefacts inside `try/except`. If
   they are missing or corrupt, it logs a warning and continues with
   `model = None` — the app still serves full rule-based analysis.
6. `uploads/` is created if absent.

**Verified:** the module imports cleanly with no `.env`, no MySQL, and no SMTP
server. This is what CI relies on — see
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

---

## Request flow

| Method | Route | Auth | Responsibility |
| ------ | ----- | ---- | -------------- |
| GET | `/` | — | Upload form + searchable career selector |
| GET/POST | `/login` | — | Email + password, seeds session |
| GET/POST | `/register` | — | Gmail validation, issues OTP |
| POST | `/register/verify-otp` | — | Consumes registration OTP |
| POST | `/resend-otp` | — | Throttled OTP reissue |
| GET/POST | `/create-password` | — | Sets password post-verification |
| GET/POST | `/forgot-password` | — | Issues reset OTP |
| GET | `/verify-otp/<purpose>` | — | OTP entry screen |
| POST | `/verify-reset-otp` | — | Consumes reset OTP |
| GET/POST | `/reset-password` | — | Sets new password |
| POST | `/analyze` | ✅ | Upload + analyse a new resume |
| POST | `/analyze-existing` | ✅ | Re-score a stored resume against another career |
| GET | `/history` | ✅ | List saved analyses |
| POST | `/clear-history` | ✅ | Delete the current user's analyses |
| GET | `/history/<int:analysis_id>` | ✅ | Single analysis detail |
| GET/POST | `/profile` | ✅ | Account details |
| GET | `/logout` | — | Clears session |

Plus `413`, `404`, and `500` error handlers rendering `error.html`.

---

## Analysis pipeline

This is the core of the product. Note where the model is **optional**.

```mermaid
flowchart TD
    A["Uploaded file<br/>.pdf / .docx, max 10 MB"] --> B{"Extension"}
    B -->|".pdf"| C["PyMuPDF get_text per page"]
    B -->|".docx"| D["python-docx<br/>paragraphs + tables"]

    C --> E{"Extracted<br/>text >= 50 chars?"}
    E -->|yes| G["clean_text()"]
    E -->|"no — scanned PDF"| F["OCR fallback: render page at 2x,<br/>Pillow image, Tesseract --oem 3 --psm 6"]
    F --> G
    D --> G

    G --> H["normalize() lowercase + collapse whitespace"]
    H --> I["detect_skills()<br/>word-boundary regex over 167 skills<br/>plus SKILL_ALIASES"]
    H --> J["section_lines()<br/>education · projects<br/>experience · certifications"]

    I --> K["resume_score()<br/>weighted, capped at 100"]
    I --> L["career_match(role, skills)<br/>matched / required x 100"]
    J --> K

    H -.-> M["ml_prediction()<br/>TF-IDF transform then predict"]
    M -.->|"career + probability x 100"| N

    I --> N["analyze_text() result dict"]
    J --> N
    K --> N
    L --> N

    L --> O["missing skills"]
    O --> P["priority High / Medium / Low"]
    O --> Q["LEARNING_TOPICS lookup, 42 skills"]
    N --> R["CAREER_ROADMAPS[role]"]
    N --> S["PROJECTS[role]"]

    P --> T["result.html"]
    Q --> T
    R --> T
    S --> T
    N --> U[("INSERT resume_analysis")]
    U --> T
```

### Deterministic vs learned

| Capability | Mechanism | Deterministic? |
| ---------- | --------- | -------------- |
| Text extraction | PyMuPDF / python-docx / Tesseract | ✅ Yes |
| Skill detection | Word-boundary regex + alias map | ✅ Yes |
| Section parsing | Heading-alias line matching | ✅ Yes |
| Resume score | Fixed weighted formula | ✅ Yes |
| Career match % | Set intersection ratio | ✅ Yes |
| Skill priority, topics, roadmap, projects | Catalogue dict lookups | ✅ Yes |
| **Career suggestion + confidence** | **TF-IDF + Logistic Regression** | ❌ Learned (auxiliary) |

Most of the product is **deterministic and explainable**; the learned model
contributes one advisory field. See [ml-pipeline.md](ml-pipeline.md).

---

## Authentication and OTP flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Flask
    participant D as MySQL
    participant M as Gmail SMTP

    B->>F: POST /register (gmail only)
    F->>F: valid_gmail() regex check
    F->>F: secrets.randbelow(1000000) gives 6-digit OTP
    F->>D: INSERT otp_tokens (otp_hash, expires_at, purpose=register)
    F->>M: send_otp() via SMTP 587 STARTTLS
    F-->>B: redirect to OTP entry
    M-->>B: email containing raw OTP
    B->>F: POST /register/verify-otp
    F->>D: SELECT latest token, verify hash
    Note over F,D: expiry 90s · max 5 attempts · 30s cooldown<br/>consumed_at stamped on success
    F->>F: session registration_verified = True
    B->>F: POST /create-password
    F->>D: INSERT users (generate_password_hash)
    F-->>B: logged in
```

The same machinery serves password reset under `purpose='reset'`. The raw OTP
is never persisted — only its hash.

---

## Data model

Four tables, defined in [`database.sql`](../database.sql). Column-level
reference in [database-schema.md](database-schema.md).

```mermaid
erDiagram
    users ||--o{ resumes : "owns"
    users ||--o{ resume_analysis : "has"
    resumes ||--o{ resume_analysis : "analysed as"

    users {
        int id PK
        varchar_100 name
        varchar_150 email UK
        varchar_255 password "werkzeug hash"
        timestamp created_at
    }
    otp_tokens {
        bigint id PK
        varchar_150 email "not an FK"
        enum purpose "register or reset"
        varchar_255 otp_hash
        datetime expires_at
        int attempts
        datetime consumed_at
        timestamp created_at
    }
    resumes {
        int id PK
        int user_id FK
        varchar_255 original_filename
        varchar_255 stored_filename UK
        timestamp created_at
    }
    resume_analysis {
        int id PK
        int user_id FK
        int resume_id FK
        varchar_255 filename
        varchar_120 target_career
        decimal resume_score
        decimal match_percentage
        text matched_skills
        text missing_skills
        text score_breakdown
        timestamp created_at
    }
```

`otp_tokens.email` is deliberately **not** a foreign key: reset OTPs must work
while a password is changing, and registration OTPs exist before the `users`
row does.

---

## Technology responsibilities

| Component | Role |
| --------- | ---- |
| **Flask** | Routing, sessions, templating, upload handling, error pages |
| **Flask-Mail** | SMTP delivery of OTP emails |
| **mysql-connector-python** | Direct DB-API access — no ORM |
| **PyMuPDF** | PDF text extraction; rasterises pages for OCR |
| **Pillow** | In-memory bridge between PyMuPDF pixmaps and Tesseract |
| **Tesseract OCR** | Text recovery for image-only PDFs |
| **python-docx** | DOCX paragraph and table extraction |
| **scikit-learn** | `TfidfVectorizer` + `LogisticRegression` for the advisory model |
| **joblib** | Serialising and loading model artefacts |
| **python-dotenv** | Loading `.env` into the environment |
| **Werkzeug** | Password hashing, filename sanitisation |
| **Jinja2** | Server-rendered templates — no frontend framework |

**Deliberately absent:** JavaScript build tooling, an ORM, a REST/JSON API, a
task queue, Redis, Docker, and a model-serving service. Adding these is a
design decision, not an oversight.

---

## Extension points

Where new work belongs, in rough order of ease:

| Change | Location |
| ------ | -------- |
| New career + required skills | `CAREERS` |
| New roadmap stages | `CAREER_ROADMAPS` |
| New recommended projects | `PROJECTS` |
| New learning topics | `LEARNING_TOPICS` |
| Better skill recall | `SKILL_ALIASES` |
| Score weighting | `resume_score()` |
| Section-heading variants | `section_lines()` alias map |
| Retrained model | `ml_training/train_model.py` |
| Schema change | `database.sql` (add `ALTER` notes) |

---

## Scaling and structural limits

Being candid about these is more impressive than hiding them:

- **Single module.** 5,000 lines in one file makes ownership and testing hard.
  Splitting into Flask blueprints is the natural first refactor.
- **Synchronous OCR.** A dense scanned PDF occupies a request worker for the
  whole OCR pass; a task queue would be needed under real load.
- **Disk-bound uploads.** `uploads/` does not scale horizontally without
  shared object storage.
- **No connection pooling.** A fresh MySQL connection is opened per call.
- **No analysis cache.** Re-running the same resume and career recomputes.
- **Session auth only.** No tokens, so no programmatic API consumers.

None of these are bugs at portfolio scale — they are the boundaries of the
current design.

---

## Related documents

- [ml-pipeline.md](ml-pipeline.md) — the model in detail, including its limits
- [database-schema.md](database-schema.md) — column reference and constraints
- [SECURITY.md](../SECURITY.md) — implemented protections
- [demo/README.md](demo/README.md) — the canonical end-to-end recording flow
