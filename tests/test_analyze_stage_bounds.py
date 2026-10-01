"""Regression tests for the production Analyze-flow fix.

Run with:

    python -m unittest discover -s tests -v

Root cause covered here: /analyze does every stage synchronously before
any byte reaches the browser, and OCR (the only stage with no natural
bound) could hold the request open past the client watchdog on a small
production instance — after which the user's retry discards the
finished server response and the browser stays stuck on the Analyze
page while Render logs a 200.

These tests pin the three fixes:

1. OCR is bounded (page cap, text target, rasterised-page size cap) and
   only runs on the pages that actually need it: pages with their own
   text layer keep that text, uniform blank pages are skipped, and no
   page is ever OCR'd twice.
2. Every /analyze stage emits a redacted timing line, and failures log
   the stage plus a full traceback — never resume contents, personal
   data, or the original filename.
3. Failure paths stay visible: redirect + flash + retry, never a
   silent 200 of the Analyze page.

Nothing here touches Supabase: outbound calls are stubbed and the
connection URLs point at a closed local port for the whole process.
"""

import io
import os
import unittest
from unittest import mock

# The external services must never be reachable from tests. Importing
# app.py calls load_dotenv(), which does NOT override variables that
# are already set in the process, so these values win over the real .env.
os.environ["SUPABASE_URL"] = "http://127.0.0.1:9"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-not-a-real-key"
os.environ["SUPABASE_DB_URL"] = "postgresql://test:test@127.0.0.1:9/test"
os.environ["SECRET_KEY"] = "test-only-secret-key"

import pymupdf  # noqa: E402

import app as resume_app  # noqa: E402

SECRET_TOKEN = "ZQXTOKEN98765SECRETIVE"
SECRET_FILENAME = "Jane_Doe_Confidential_Resume.pdf"

RESUME_TEXT = f"""Jane Doe
Email: jane.doe@example.com | Phone: +91 9876543210

Professional Summary
Backend developer with Python experience. {SECRET_TOKEN}

Technical Skills
Python, Flask, SQL, Git, Docker, REST API, JavaScript

Education
B.Tech Computer Science, Sample Institute of Technology, 2021

Work Experience
Software Engineer at Sample Software Pvt Ltd, 2021-2023

Projects
Resume Analyzer web application built with Flask and PostgreSQL
"""


def text_pdf_bytes():
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((40, 50), RESUME_TEXT, fontsize=9)
    data = document.tobytes()
    document.close()
    return data


def blank_pdf_bytes(pages):
    """An image-free multi-page PDF: no extractable text and perfectly
    uniform pages, so extraction must skip them without OCR."""
    document = pymupdf.open()
    for _ in range(pages):
        document.new_page()
    data = document.tobytes()
    document.close()
    return data


def scan_pdf_bytes(page_sizes):
    """Scan-like pages of the given sizes: a black bar instead of a text
    layer, so each page needs OCR (and never a perfectly uniform one)."""
    document = pymupdf.open()
    for width, height in page_sizes:
        page = document.new_page(width=width, height=height)
        page.draw_rect(
            pymupdf.Rect(40, 40, width - 40, 120),
            color=None,
            fill=(0, 0, 0),
        )
    data = document.tobytes()
    document.close()
    return data


def mixed_pdf_bytes():
    """Page 1 carries a small real text layer; page 2 is a scan."""
    document = pymupdf.open()
    text_page = document.new_page()
    text_page.insert_text(
        (40, 50), "Career Objective: backend engineer", fontsize=9
    )
    scan_page = document.new_page()
    scan_page.draw_rect(
        pymupdf.Rect(40, 40, 500, 120), color=None, fill=(0, 0, 0)
    )
    data = document.tobytes()
    document.close()
    return data


def chaff_pdf_bytes():
    """Text long enough to skip OCR but with no resume sections."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text(
        (40, 50),
        "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do "
        "eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        fontsize=9,
    )
    data = document.tobytes()
    document.close()
    return data


TEXT_PDF = text_pdf_bytes()
CHAFF_PDF = chaff_pdf_bytes()


def write_upload(data):
    """Write fixture bytes to a temporary upload file, return its path."""

    import tempfile

    handle = tempfile.NamedTemporaryFile(
        suffix=".pdf",
        dir=str(resume_app.UPLOAD_FOLDER),
        delete=False,
    )
    handle.write(data)
    handle.close()

    path = resume_app.Path(handle.name)

    return path


class OcrBoundTests(unittest.TestCase):

    """The stage that could hold /analyze open forever is now bounded."""

    def test_page_cap_stops_a_long_scan(self):

        calls = []

        def fake_ocr(image, config=""):

            calls.append(1)

            # Yield very little text so the target never triggers:
            # only the page cap can stop the loop.
            return "Education\n"

        with mock.patch.object(
            resume_app.pytesseract,
            "image_to_string",
            side_effect=fake_ocr,
        ):

            with self.assertLogs(resume_app.logger, level="INFO") as captured:

                path = write_upload(
                    scan_pdf_bytes(
                        [(595, 842)]
                        * (resume_app.MAX_OCR_PAGES + 5)
                    )
                )

                try:

                    resume_app.extract_resume(path)

                finally:

                    resume_app.remove_uploaded_file(path)

        self.assertEqual(
            len(calls),
            resume_app.MAX_OCR_PAGES,
        )

        logged = "\n".join(captured.output)

        self.assertIn("OCR summary", logged)
        self.assertIn("page_cap_hit=True", logged)

        # Recognised document text must not be echoed on the summary
        # line itself.
        summary = next(
            line
            for line in captured.output
            if "OCR summary" in line
        )
        self.assertNotIn("Education", summary)

    def test_ocr_stops_once_enough_text_is_recognised(self):

        calls = []

        def fake_ocr(image, config=""):

            calls.append(1)

            return "y" * 1500

        with mock.patch.object(
            resume_app.pytesseract,
            "image_to_string",
            side_effect=fake_ocr,
        ):

            with self.assertLogs(resume_app.logger, level="INFO") as captured:

                path = write_upload(
                    scan_pdf_bytes(
                        [(595, 842)]
                        * (resume_app.MAX_OCR_PAGES + 5)
                    )
                )

                try:

                    resume_app.extract_resume(path)

                finally:

                    resume_app.remove_uploaded_file(path)

        # 1500 chars/page: the 4000-char target is reached on page 3,
        # long before the page cap.
        self.assertEqual(len(calls), 3)
        self.assertIn(
            "target_hit=True",
            "\n".join(captured.output),
        )

    def test_pages_with_a_text_layer_are_not_ocrd(self):

        calls = []

        def fake_ocr(image, config=""):

            calls.append(image.size)

            return "z" * 120

        with mock.patch.object(
            resume_app.pytesseract,
            "image_to_string",
            side_effect=fake_ocr,
        ):

            with self.assertLogs(resume_app.logger, level="INFO") as captured:

                path = write_upload(
                    mixed_pdf_bytes()
                )

                try:

                    text = resume_app.extract_resume(path)

                finally:

                    resume_app.remove_uploaded_file(path)

        # Only the scan page reaches Tesseract. The page with its own
        # text layer keeps that text instead of being rasterised, and
        # the kept text still reaches the analysis.
        self.assertEqual(len(calls), 1)
        self.assertIn("Career Objective", text)
        self.assertIn("z" * 120, text)

        self.assertIn(
            "text_pages=1",
            "\n".join(captured.output),
        )

    def test_uniform_blank_pages_never_reach_tesseract(self):

        calls = []

        def fake_ocr(image, config=""):

            calls.append(image.size)

            return "y" * 100

        with mock.patch.object(
            resume_app.pytesseract,
            "image_to_string",
            side_effect=fake_ocr,
        ):

            with self.assertLogs(resume_app.logger, level="INFO") as captured:

                path = write_upload(
                    blank_pdf_bytes(3)
                )

                try:

                    resume_app.extract_resume(path)

                finally:

                    resume_app.remove_uploaded_file(path)

        # A perfectly uniform page cannot contain text: no OCR process
        # is started for any of them.
        self.assertEqual(calls, [])

        summary = next(
            line
            for line in captured.output
            if "OCR summary" in line
        )

        self.assertIn("pages=0", summary)
        self.assertIn("blank_pages=3", summary)

    def test_every_needing_page_is_ocrd_exactly_once(self):

        sizes = [(595, 842), (500, 700), (612, 792)]

        calls = []

        def fake_ocr(image, config=""):

            calls.append(image.size)

            return "q" * 100

        with mock.patch.object(
            resume_app.pytesseract,
            "image_to_string",
            side_effect=fake_ocr,
        ):

            with self.assertLogs(resume_app.logger, level="INFO"):

                path = write_upload(
                    scan_pdf_bytes(sizes)
                )

                try:

                    resume_app.extract_resume(path)

                finally:

                    resume_app.remove_uploaded_file(path)

        # One OCR run per page and never a page twice: the distinct
        # page sizes make every raster size unique, so a repeated OCR
        # run on any page would show up as a duplicate.
        self.assertEqual(len(calls), len(sizes))
        self.assertEqual(len(set(calls)), len(sizes))

    def test_page_raster_is_bounded(self):

        # Separate documents: pymupdf orphans live page handles when a
        # document grows, so each rect must be read from its own file.
        huge_doc = pymupdf.open()
        huge = huge_doc.new_page(width=5000, height=7000)

        zoom = resume_app.ocr_zoom_for_page(huge)

        self.assertLessEqual(
            huge.rect.width * zoom,
            resume_app.OCR_MAX_PAGE_DIMENSION + 0.01,
        )
        self.assertLessEqual(
            huge.rect.height * zoom,
            resume_app.OCR_MAX_PAGE_DIMENSION + 0.01,
        )

        huge_doc.close()

        normal_doc = pymupdf.open()
        normal = normal_doc.new_page(width=612, height=792)

        # Normal letter pages keep the historical 2x zoom.
        self.assertEqual(
            resume_app.ocr_zoom_for_page(normal),
            2.0,
        )

        normal_doc.close()

    def test_bounds_have_safe_defaults(self):

        self.assertGreaterEqual(resume_app.MAX_OCR_PAGES, 1)
        self.assertGreaterEqual(resume_app.OCR_TARGET_CHARS, 1)
        self.assertGreaterEqual(resume_app.OCR_MAX_PAGE_DIMENSION, 1)


class AnalyzeStageLoggingTests(unittest.TestCase):

    """Each stage logs its duration; nothing sensitive ever appears."""

    def setUp(self):

        self.client = resume_app.app.test_client()

        for patcher in (
            mock.patch.object(
                resume_app, "get_user_resumes", return_value=[]
            ),
            mock.patch.object(
                resume_app,
                "upload_resume_to_storage",
                return_value="1/stored.pdf",
            ),
            mock.patch.object(
                resume_app,
                "save_resume_and_analysis",
                return_value=(1, 1),
            ),
        ):

            patcher.start()
            self.addCleanup(patcher.stop)

        with self.client.session_transaction() as session:

            session["user_id"] = 1

    def analyze(self, payload, filename, content_type):

        return self.client.post(
            "/analyze",
            data={
                "target_role": "Software Engineer",
                "resume": (io.BytesIO(payload), filename, content_type),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    def test_success_emits_a_timing_line_per_stage(self):

        with self.assertLogs(resume_app.logger, level="INFO") as captured:

            response = self.analyze(
                TEXT_PDF,
                SECRET_FILENAME,
                "application/pdf",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Analysis Result",
            response.get_data(as_text=True),
        )

        logged = "\n".join(captured.output)

        for expected in (
            "analyze.start user_id=",
            "stage=save_file ms=",
            "stage=extract ms=",
            "stage=validate_content ms=",
            "stage=predict ms=",
            "stage=storage ms=",
            "stage=db_save ms=",
            "analyze.done status=200 total_ms=",
        ):

            self.assertIn(expected, logged)

        # Redaction: no resume contents, no original filename.
        self.assertNotIn(SECRET_TOKEN, logged)
        self.assertNotIn(SECRET_FILENAME, logged)
        self.assertNotIn("jane.doe@example.com", logged)

    def test_invalid_content_rejects_with_redirect_and_stage_log(self):

        with self.assertLogs(resume_app.logger, level="INFO") as captured:

            response = self.client.post(
                "/analyze",
                data={
                    "target_role": "Software Engineer",
                    "resume": (
                        io.BytesIO(CHAFF_PDF),
                        "notes.pdf",
                        "application/pdf",
                    ),
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )

        # The followed redirect lands back on the Analyze page with a
        # flash — the failure is visible, not a silent 200.
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Invalid file. Please upload a valid resume.",
            response.get_data(as_text=True),
        )

        logged = "\n".join(captured.output)
        self.assertIn("stage=validate_content", logged)
        self.assertIn("valid=False", logged)

    def test_read_failure_logs_stage_and_redirects_to_retry(self):

        with self.assertLogs(resume_app.logger, level="ERROR") as captured:

            response = self.client.post(
                "/analyze",
                data={
                    "target_role": "Software Engineer",
                    "resume": (
                        io.BytesIO(b"this is not a pdf"),
                        "broken.pdf",
                        "application/pdf",
                    ),
                },
                content_type="multipart/form-data",
            )

        # The route never answers 200 with the Analyze page on failure:
        # it redirects, and the flash renders on the next GET.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

        followed = self.client.get(response.headers["Location"])

        self.assertIn(
            "could not read this file",
            followed.get_data(as_text=True),
        )

        logged = "\n".join(captured.output)
        self.assertIn("stage=extract", logged)
        self.assertIn("Resume file could not be read", logged)

    def test_missing_role_is_a_redirect_with_a_visible_message(self):

        response = self.client.post(
            "/analyze",
            data={},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 302)

        followed = self.client.get("/")

        self.assertIn(
            "Please choose a valid career.",
            followed.get_data(as_text=True),
        )


class WatchdogRetryMessageTests(unittest.TestCase):

    """The stage-2 message must not pretend a retry is free: a second
    submit aborts the still-pending request, discarding its response."""

    def test_stage_two_message_explains_retry_starts_over(self):

        index_path = os.path.join(
            resume_app.app.root_path,
            "templates",
            "index.html",
        )

        with open(index_path, encoding="utf-8") as handle:

            html = handle.read()

        # Pinned by test_analyze_button_resilience: the stage-2 notice
        # keeps its leading phrase and hands the button back first.
        self.assertIn("taking longer than usual", html)
        self.assertIn("starts a new attempt", html)


if __name__ == "__main__":

    unittest.main()

