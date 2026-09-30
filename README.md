# AI Resume Analyzer

A Flask + Supabase (PostgreSQL) resume analysis application with email OTP registration, password reset, target-career matching, skill-gap analysis, learning topics, career roadmaps, project recommendations and per-user history.

## Run locally
1. Do not include `venv/` or real `.env` secrets in a ZIP/Git repository.
2. Create a virtual environment: `python -m venv venv`
3. Activate it: Windows `venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Create the tables in your Supabase PostgreSQL database (`users`, `otp_tokens`, `resumes`, `resume_analysis`).
6. Copy `.env.example` to `.env`, add your Supabase database password (`SUPABASE_DB_PASSWORD`) or connection string, and fill in your SMTP values.
7. Start: `python app.py`

### Gmail
Use a Gmail App Password for `MAIL_PASSWORD`; never put the real value in GitHub or the project ZIP.

### Tesseract
Scanned-PDF OCR requires Tesseract OCR installed on the machine and available on PATH (or configured through your OS). Text-based PDFs and DOCX resumes never need it. When Tesseract is missing — for example on a native Python host such as Render, which does not ship it — a scanned/image-only PDF is handled gracefully: the page explains that the PDF looks scanned and asks for a text-based PDF or DOCX instead of failing with a generic "Unable to analyze this resume right now." error.

## Production notes
Set `FLASK_DEBUG=false`, use a strong `SECRET_KEY`, keep `.env` private, use HTTPS, and configure the production WSGI server/database.

Production is deployed from the repository's [Dockerfile](Dockerfile): the image installs Tesseract OCR with its English language data and runs Gunicorn bound to Render's `$PORT`, so scanned/image-only PDFs are analysed in production too. Step-by-step Render switch-over instructions live in [docs/deployment.md](docs/deployment.md).
