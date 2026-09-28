# Demo recording guide

The canonical end-to-end flow for recording a demo, GIF or screenshot set —
every feature, in order, with **zero real personal data** on screen.

> One take is ~4 minutes: registration with OTP, analysis, history, profile, and
> the password-reset lane. The screenshots that ship with the README are made
> from synthetic data only; see [SECURITY.md](../../SECURITY.md) for why.

---

## Pre-flight checklist

| Check | Why |
| ----- | --- |
| `.env` has the Supabase database password or connection string | Without it every DB step fails with "Unable to login right now. Check database configuration." |
| `.env` has `MAIL_USERNAME` / `MAIL_PASSWORD` (Gmail App Password) | Registration is Gmail-only and the OTP is delivered by email |
| Supabase tables exist (`users`, `otp_tokens`, `resumes`, `resume_analysis`) | See [../database-schema.md](../database-schema.md) |
| A **throwaway Gmail account** you are happy to show, or plan to mask it | The OTP email screenshot shows the recipient address |
| A **synthetic resume** (`.pdf` or `.docx`, ≤ 10 MB) | Never a real CV — [SECURITY.md](../../SECURITY.md) |
| Tesseract on `PATH` | Only needed if you demo an image-only (scanned) PDF |
| `FLASK_DEBUG=false` | Clean startup logs and no reloader banner |
| Fresh browser profile / cleared cookies, window ~1280×800 | No stray tabs, bookmarks or old sessions |
| History cleared (or a fresh account) | So the history page shows only what you just did |

---

## The canonical flow

### 1. Register — `/register`

- Fill **name** and a Gmail address, submit **Create Account**.
- If the address is already registered you are sent to login instead — use a
  fresh address (or the `+tag` trick) for the demo.

### 2. The OTP email

- A 6-digit code arrives within seconds; it is valid for **90 seconds**.
- Show the message, but **mask the sender and recipient addresses** and any
  Gmail chrome that reveals them.

### 3. Verify the OTP — `/register/verify-otp`

- Page heading: **Enter your OTP** → button **Verify OTP**.
- The countdown is server-side; if it expires, use resend (30-second cooldown).

### 4. Create the password — `/create-password`

- Page heading: **Create password** — minimum 8 characters, confirmation must
  match. Use something obviously demo-safe (e.g. `Demo-Passw0rd`).

### 5. Log in — `/login`

- Page heading: **Welcome back** — the login page is also what the demo returns
  to after a password reset.

### 6. Analyse a resume — `/` (home)

- Sections: **Upload your resume**, **Choose target career**, **Recent resumes**.
- Pick any of the 40 careers, attach the synthetic resume, submit.
- The file is validated as a resume (≥ 3 recognised sections, or 2 sections plus
  contact details and 2 skills). A random PDF is rejected with
  *"Invalid file. Please upload a valid resume."*

### 7. The result page

Headings you will capture, in order:

| Section | Shows |
| ------- | ----- |
| `{{ role }}` | Target career for this run |
| Resume score / match % | Weighted score out of 100 and match against the career |
| **Skills you have** | Matched skills |
| **Skills to learn** | Gaps |
| **What should you learn first?** | Priority skill |
| **What else should you learn?** | Remaining learning topics |
| **`{{ role }}` — Job Ready Path** | Roadmap stages |
| **Projects to build** | Suggested portfolio projects |
| **Make your resume stronger** | Per-section score breakdown, plus the advisory ML career suggestion and its confidence |

The suggested-career field is the only learned/statistical output on the page —
see [../ml-pipeline.md](../ml-pipeline.md) before quoting anything about it.

### 8. History — `/history`

- Page heading: **Compare your career matches.** — one row per run with score,
  match % and the best-match ("recommended") flag per resume.
- Click a row to reopen the full result; the stored file is re-analysed, which
  proves persistence rather than a cached page.
- The **clear history** button deletes the signed-in user's analysis rows,
  resume rows and uploaded files in one action — a good closing beat if you
  demo the same account twice.

### 9. Re-analyse an existing resume

- From the home page **Recent resumes**, pick a stored file, choose a different
  target career and analyse again — the same resume now has two history rows.

### 10. Profile — `/profile`

- Page heading: **Your profile** — change the display name to show the
  `UPDATE`, then confirm the new name appears in the navigation.

### 11. Forgotten password lane

| Step | Route | Heading / button |
| ---- | ----- | ---------------- |
| Request a reset code | `/forgot-password` | **Forgot password?** |
| Verify | `/verify-otp/reset` | **Enter your OTP** → **Verify OTP** |
| Set a new password | `/reset-password` | **Create new password** → **Change Password** |
| Log in again | `/login` | **Welcome back** |

The response is deliberately vague about whether an account exists ("If an
account exists for that email…") — mention that if you narrate the demo.

### 12. Log out — `/logout`

- Ends the session; the demo is over.

---

## Shot list

| # | Capture | Route | Notes |
| - | ------- | ----- | ----- |
| 1 | Landing login page | `/login` | Sets the visual tone |
| 2 | Registration form | `/register` | Synthetic name + throwaway Gmail |
| 3 | OTP email | — | **Mask addresses** |
| 4 | OTP entry + success | `/register/verify-otp` | Shows the timer |
| 5 | Password creation | `/create-password` | Never type your real password on camera |
| 6 | Home page with career picker | `/` | Show the career list breadth (40 careers) |
| 7 | Progress during analysis | `/analyze` | Fast on a text PDF; seconds longer with OCR |
| 8 | Result page (top) | — | Score + match % |
| 9 | Result page (skills + priority) | — | The product's core value |
| 10 | Roadmap + projects | — | Screenshot for the README |
| 11 | History + detail reopen | `/history` | Proves persistence |
| 12 | Profile update | `/profile` | Quick DB write proof |
| 13 | Reset lane | `/forgot-password` | Optional but shows completeness |

## Redaction rules

- **Synthetic resume only.** No real names, phone numbers, employer names,
  personal emails or addresses. CI fails the build if a resume file is committed.
- **Mask the Gmail address** in the OTP screenshot (sender *and* recipient).
- **Never show** `.env`, a terminal containing credentials, the Supabase
  dashboard, the database password, or a `postgresql://` connection string.
- **Never show** the browser's password manager, autofill dropdowns or saved
  profiles.
- Anything shown in history must be your own synthetic filename.
- If you demo on Windows with notifications enabled, turn them off first.

## Where the assets live

| Asset | Location |
| ----- | -------- |
| Screenshots / GIFs / clips | `docs/demo/` (this folder) — keep each file small and web-friendly |
| Shared branding (existing) | [../assets/banner.svg](../assets/banner.svg) |
| Uploaded resumes | `uploads/` at the repository root — **gitignored, never committed** |

Reference an image from the README with a repository-root-relative path — for
example an analysis GIF saved in this folder as `docs/demo/analysis.gif` — and
keep the filenames lowercase and descriptive (`register-otp.gif`,
`result-roadmap.png`).

## Timing notes

- The OTP lives **90 seconds**; request it immediately before recording that
  step or record it as its own take.
- Resending is throttled to one request per **30 seconds** per address.
- OCR on a dense scanned PDF takes seconds — trim that wait in the GIF.
- Uploads are capped at **10 MB** and only `.pdf` / `.docx` are accepted.

## If something goes wrong on camera

| Symptom | Cause / fix |
| ------- | ----------- |
| "Unable to login right now. Check database configuration." | The Supabase connection string or database password is missing from `.env` |
| OTP never arrives | Gmail App Password missing/expired, or the address is not a Gmail address (registration is Gmail-only) |
| "OTP expired. Please request a new OTP." | More than 90 seconds elapsed between sending and entering |
| "Too many incorrect attempts." | 5 wrong codes consumed the token — resend |
| "Invalid file. Please upload a valid resume." | The document did not look like a resume; use a real synthetic CV with skills, education and projects |
| "Only PDF and DOCX files are supported." / 413 page | Wrong extension, or the file exceeds 10 MB |
| Blank analysis on a scanned PDF | Tesseract is not installed or not on `PATH` |

---

## Related documents

- [../architecture.md](../architecture.md) — what each page is doing behind the scenes
- [../database-schema.md](../database-schema.md) — where the captured data is stored
- [../ml-pipeline.md](../ml-pipeline.md) — the advisory career suggestion
- [../../SECURITY.md](../../SECURITY.md) — what must never appear in a screenshot
- [../../CONTRIBUTING.md](../../CONTRIBUTING.md) — local setup and PR expectations
