# Contributing to AI Resume Analyzer

Thanks for taking an interest. Contributions are welcome — and because the
codebase is intentionally a **single-file Flask application**, you can get
oriented in about ten minutes.

---

## Before you start

Read [`SECURITY.md`](SECURITY.md) first. The most important rule: **never
commit `.env`, real credentials, or real resume files.**

You'll need **Python 3.10+**, a **MySQL** server, and — for scanned-PDF OCR —
**Tesseract OCR** on your `PATH`. Full setup is in the
[README](README.md#-getting-started).

---

## The five-step workflow

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/ai-resume-.git
cd ai-resume-
```

### 2. Create a branch

```bash
git checkout -b feature/skill-gap-weighting
```

Use a short prefix: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`.

### 3. Set up your environment

```bash
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
copy .env.example .env         # then edit .env with your values
mysql -u root -p < database.sql

python app.py
```

### 4. Make your change

- Keep `python -m compileall app.py ml_training` clean.
- Match the file's existing style. `app.py` uses a wide, heavily vertical
  layout (one argument per line); it is consistent throughout, so please keep
  new code consistent too.
- Data catalogs (`CAREERS`, `CAREER_ROADMAPS`, `LEARNING_TOPICS`, `PROJECTS`)
  are plain Python dicts — extending them is the easiest useful contribution.
- Never run `git add -A` blindly. Check `git status` and confirm no resume
  files or `.env` are staged.

### 5. Test, then commit

Confirm the manual flow still works end to end:

> register → OTP → create password → upload resume → select career → result →
> history → profile

```bash
git add <files>
git commit -m "feat: weight missing-skill priority by career relevance"
git push -u origin feature/skill-gap-weighting
```

Conventional Commit prefixes (`feat:`, `fix:`, `docs:`, `refactor:`) keep the
history readable.

---

## Opening a pull request

Open a PR against `main` and fill in the template. Please include:

- **What** changed and **why**.
- **How you tested it** — the manual flow above, or which routes you hit.
- **Screenshots** if anything renders differently.
- Any **breaking change**, including anything that alters `database.sql`.

---

## Good first contributions

Genuinely approachable, and no design debate required:

- More entries in `SKILL_ALIASES` so `C++`, `node js`, or `js` resolve
  correctly.
- New careers, roadmaps, or recommended projects in the catalog dicts.
- A **synthetic** sample resume under `docs/demo/` for testing.
- Documentation and typo fixes.

## Please don't

- Don't rewrite the Git history or force-push.
- Don't add a test framework, frontend build step, or new database until
  discussion opens one up — the project is deliberately dependency-light.
- Don't reformat `app.py` wholesale; huge style-only diffs hide real changes.
- Don't claim model accuracy without a held-out evaluation set.

---

## A note on style

`app.py` is one very long module and several templates carry large inline
style blocks. That structure is a deliberate part of this project's history and
is **not** up for debate in drive-by PRs. Refactoring proposals are welcome as
a [discussion][discussions] or an issue first, not as a pull request that
rewrites everything.

[discussions]: https://github.com/abinesh-0/ai-resume-/discussions

Questions? Open an [issue][issues].

[issues]: https://github.com/abinesh-0/ai-resume-/issues
