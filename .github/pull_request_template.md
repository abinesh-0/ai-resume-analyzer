<!--
Thanks for contributing to AI Resume Analyzer!

Before you submit, please confirm:
  - No `.env`, credential, or resume file is included in the diff.
  - `python -m compileall -q app.py ml_training` is clean.
  - The register → OTP → upload → analyze → history flow still works.

You can delete this comment block.
-->

## What changed?

<!-- One or two sentences describing the change itself. -->

## Why?

<!-- The problem it solves. Link an issue with `Closes #123` if applicable. -->

Closes #

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Career catalogue / roadmap / learning-topic content
- [ ] Skill alias or skill-detection improvement
- [ ] Documentation only
- [ ] Refactor (no behaviour change)

## Areas touched

- [ ] `app.py` routes or analysis logic
- [ ] Career catalogues (`CAREERS` / `CAREER_ROADMAPS` / `LEARNING_TOPICS` / `PROJECTS`)
- [ ] Templates (`templates/`)
- [ ] Static assets (`static/`)
- [ ] `database.sql` schema
- [ ] ML training (`ml_training/`) or model artefacts (`models/`)
- [ ] Documentation / CI only

## Testing completed

- [ ] `python -m compileall -q app.py ml_training` succeeds
- [ ] App starts with `python app.py`
- [ ] Registration + OTP + password creation flow works
- [ ] Uploaded a **synthetic** resume and the result page renders
- [ ] History and profile pages still work
- [ ] Log shows no new errors or tracebacks

**Environment:** Python `____` · MySQL `____` · OS `____`

## Screenshots

Required if anything visible changed. Use a **synthetic sample resume** — never
a real document containing someone's name, phone number, or email.

## Breaking changes

- [ ] No breaking changes
- [ ] Yes — describes below, and requires a `database.sql` migration note

<!-- If breaking, explain what existing users must do (e.g. re-run schema, add
     a new key to .env, retrain the model). -->

## Checklist

- [ ] No secrets, `.env` contents, or real resumes anywhere in the diff
- [ ] Followed [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- [ ] No unrelated reformatting of `app.py`
- [ ] Updated `CHANGELOG.md` if the change is user-visible
