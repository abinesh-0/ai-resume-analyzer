# Deployment

Production runs the app from the repository's `Dockerfile`: a
`python:3.13-slim` image carrying Flask, Gunicorn, **Tesseract OCR** and
its **English language data**. Render's native Python runtime cannot
install OS-level packages, so scanned/image-only PDFs previously stopped
at "This resume looks like a scanned/image PDF..." — the image removes
that limitation.

## What the image contains

| Piece | Why |
| ----- | --- |
| `python:3.13-slim-bookworm` | Matches the Python versions covered by CI (3.11–3.13) |
| `tesseract-ocr` + `tesseract-ocr-eng` | The OCR binary plus English trained data for the scanned-PDF fallback |
| `pip install -r requirements.txt` | Flask, Gunicorn, PyMuPDF, python-docx, pytesseract, scikit-learn, psycopg, Flask-Mail, Pillow |
| Build-time OCR check | `pytesseract.get_languages()` must list `eng`, so a broken install fails the build — not the first scanned upload |
| Gunicorn start command | Binds `0.0.0.0:$PORT` (Render's default is 10000), 1 worker × 4 threads, 120 s timeout |

Secrets are never baked in: `.dockerignore` keeps `.env` out of the build
context, and configuration keeps arriving as Render environment
variables. pytesseract finds the binary through `PATH`
(`/usr/bin/tesseract`); the only override is the optional `TESSERACT_CMD`
environment variable for unusual installations. On startup (and in
`python app.py` logs) `ocr_status()` prints the detected Tesseract
version so you can confirm it from the Render logs.

## Verify the image locally (optional)

```
docker build -t ai-resume-analyzer .
docker run --rm ai-resume-analyzer python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
docker run --rm -p 8000:8000 --env-file .env -e PORT=8000 ai-resume-analyzer
```

Then open `http://localhost:8000`. `--env-file .env` is only for local
runs — never commit the file or bake it into an image.

## Switch the existing Render service to Docker

Render web services can be switched in place from the Dashboard
(**Settings → Build & Deploy → Source → Edit**); the same change is also
available through the Render API's *Update service* endpoint
(`serviceDetails.runtime`). If your dashboard does not offer it, use the
blue/green path below. Nothing here changes the live service by itself —
it is a checklist to follow when you are ready.

### Option A — in-place switch (one short redeploy)

1. Commit and push the `Dockerfile` and `.dockerignore` to the branch the
   service deploys from.
2. Open the service in the Render Dashboard → **Settings** → **Build &
   Deploy** → **Source** → **Edit**.
3. In the **Update Source** dialog keep the same repository and branch and
   set:
   - **Runtime**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Build Command**: clear it (the image builds itself)
   - **Start Command**: clear it (the image's `CMD` runs Gunicorn on `$PORT`)
4. Under **Settings → Health Checks**, set the health check path to
   `/login`. It answers `200` for signed-out visitors, while `/` redirects
   to the login page.
5. Save. Render builds the image and deploys it. The first build takes a
   few minutes (apt + pip); later builds reuse Docker layer caching.
6. Watch **Logs** for the Gunicorn banner and then upload a scanned PDF to
   confirm real OCR output.
7. If anything looks wrong, use **Deploys → Rollback** (or switch the
   source back) — the previous release stays available.

Keep the existing environment variables and secrets exactly as they are.
The app reads the same names as before: `SECRET_KEY`,
`SUPABASE_DB_URL`/`SUPABASE_DB_PASSWORD`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `MAIL_*`, `FLASK_DEBUG=false`. Supabase
PostgreSQL, Supabase Storage, authentication/OTP, history and Clear
History are unaffected — they are database/Storage features, not runtime
features.

### Option B — blue/green (zero-downtime, safest)

1. **New +** → **Web Service**, same repository and branch.
2. Set **Language** to `Docker`, **Dockerfile Path** to `./Dockerfile`.
3. Copy every environment variable/secret from the old service
   (Render's environment-variable tab can export/copy them).
4. Deploy and test on the new `*.onrender.com` URL: login, upload a
   scanned PDF, open History, run Clear History.
5. Move the custom domain to the new service, then delete the old one.

### Option C — Render API (for automation)

Render's *Update service* endpoint accepts the new runtime in its
`serviceDetails` parameter (`"runtime": "docker"` plus
`"dockerfilePath": "./Dockerfile"`), which is what the Dashboard uses
under the hood and what Blueprint users get from a `render.yaml` sync.

## Operational notes

- **Free-tier memory (512 MB):** the image starts one Gunicorn worker with
  four threads — scikit-learn and PyMuPDF are loaded per worker. On larger
  instances raise `--workers` in the `CMD` for CPU-parallel OCR.
- **Timeouts:** the container sets a 120 s Gunicorn timeout, which covers
  OCR of large scans.
- **Uploads are ephemeral:** resumes live in the Supabase Storage bucket,
  so container restarts or redeploys lose nothing.
- **Language data:** only English (`eng`) is installed, matching the app's
  extraction logic. Add more `tesseract-ocr-<lang>` packages to the
  Dockerfile if that ever changes.

