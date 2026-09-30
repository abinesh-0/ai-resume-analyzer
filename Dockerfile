# =============================================================
# AI Resume Analyzer — production image
# -------------------------------------------------------------
# Flask + Gunicorn packaged together with the Tesseract OCR system
# binary and its English language data, so scanned/image-only PDFs
# are analysed in production too. Render's native Python runtime
# does not provide Tesseract (it is an OS package, not a pip
# dependency), which is why the deployed app previously reported
# "OCR is not available on the server" for scanned resumes.
#
# Secrets are never baked in: configuration comes from environment
# variables, and .dockerignore keeps .env, venv/ and local uploads
# out of the build context.
# =============================================================

FROM python:3.13-slim-bookworm

# Unbuffered logs (Render captures stdout/stderr) and lighter images.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Tesseract is a system binary. Debian installs it on PATH
# (/usr/bin/tesseract) with its trained data under
# /usr/share/tesseract-ocr/*/tessdata — exactly where pytesseract
# looks by default, so no path needs to be hard-coded.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

# Local resume workspace (the repo keeps the folder via .gitkeep).
RUN mkdir -p uploads

# Fail the build — not the first scanned upload — if OCR or the
# English language data is missing from the image.
RUN python -c "import pytesseract; langs = pytesseract.get_languages(); assert 'eng' in langs, langs; print('Tesseract', pytesseract.get_tesseract_version(), 'langs:', langs)"

# Render forwards public traffic to the port in $PORT (default 10000,
# which Render also sets) on host 0.0.0.0. One worker with four
# threads keeps the free tier's 512 MB comfortable — scikit-learn and
# PyMuPDF load per worker; raise --workers on larger instances. The
# timeout covers OCR of large scans. `exec` hands Render's stop
# signals straight to Gunicorn.
EXPOSE 10000

CMD ["sh", "-c", "exec gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile -"]
