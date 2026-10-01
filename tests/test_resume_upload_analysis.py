"""Regression tests for the mobile resume upload / analysis flow.

Run with:

    python -m unittest discover -s tests -v

These tests cover the failure behind the deployed "Unable to analyze this
resume right now." message: an image-only/scanned PDF needs the Tesseract
OCR binary, which a server (for example a Render deployment) may not have
while the developer's own laptop does. They also cover mobile-shaped
multipart uploads (octet-stream MIME types, spaces, non-Latin filenames),
0-byte or corrupt downloads, and temporary-file cleanup.

Nothing here touches Supabase: the outbound database and Storage calls are
replaced with recording stubs, and the connection URLs point at a closed
local port for the whole test process.
"""

import io
import os
import re
import unittest
from unittest import mock

# The external services must never be reachable from tests. Importing
# app.py calls load_dotenv(), which does NOT override variables that are
# already set in the process, so these values win over the real .env.
os.environ["SUPABASE_URL"] = "http://127.0.0.1:9"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test-not-a-real-key"
os.environ["SUPABASE_DB_URL"] = "postgresql://test:test@127.0.0.1:9/test"
os.environ["SECRET_KEY"] = "test-only-secret-key"

import pymupdf
from PIL import Image, ImageDraw, ImageFont

import app as resume_app

RESUME_TEXT = """Abinesh R
Software Engineer
Email: abinesh.sample@gmail.com | Phone: 9876543210

Professional Summary
Backend developer with two years of Python experience building web APIs.

Technical Skills
Python, Flask, SQL, Git, Docker, REST API, JavaScript, HTML, CSS

Education
B.Tech Computer Science, Sample Institute of Technology, 2021

Work Experience
Software Engineer at Sample Software Pvt Ltd, 2021-2023

Projects
Resume Analyzer web application built with Flask and PostgreSQL
Inventory management REST API with authentication

Certifications
AWS Cloud Practitioner
"""

FLASH_RE = re.compile(r'<div class="flash (\w+)">\s*([^<]+?)\s*</div>')

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
    "Mobile/15E148 Safari/604.1"
)


def text_pdf_bytes():
    """A text-based resume PDF, the shape that always worked."""

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((40, 50), RESUME_TEXT, fontsize=9)
    data = document.tobytes()
    document.close()
    return data


def image_pdf_bytes():
    """A readable scanned resume image with no embedded PDF text."""

    image = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(image)

    text = """John Doe
Software Engineer

Email: john@example.com
Phone: 9876543210

Professional Summary
Backend developer with Python experience.

Technical Skills
Python, Flask, SQL, Git, Docker

Education
Bachelor of Engineering

Work Experience
Software Engineer
Sample Software Pvt Ltd
"""

    # Use a real TrueType font so OCR can clearly recognize the fixture.
    font = None

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
    ]

    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, 32)
            break
        except OSError:
            continue

    if font is None:
        raise RuntimeError(
            "No TrueType font available for OCR test fixture"
        )

    draw.multiline_text(
        (60, 60),
        text,
        fill="black",
        spacing=14,
        font=font,
    )

    buffer = io.BytesIO()

    # JPEG keeps the test PDF comfortably below the upload limit.
    image.save(
        buffer,
        format="JPEG",
        quality=92,
        optimize=True,
    )

    image.close()

    document = pymupdf.open()

    page = document.new_page(
        width=595,
        height=842,
    )

    page.insert_image(
        pymupdf.Rect(0, 0, 595, 842),
        stream=buffer.getvalue(),
    )

    data = document.tobytes()

    document.close()

    return data


TEXT_PDF = text_pdf_bytes()
IMAGE_PDF = image_pdf_bytes()


class AnalyzeUploadTests(unittest.TestCase):

    """End-to-end /analyze behaviour with stubbed outbound services."""

    @classmethod
    def setUpClass(cls):

        cls.client = resume_app.app.test_client()

    def setUp(self):

        storage_patch = mock.patch.object(
            resume_app,
            "upload_resume_to_storage",
            side_effect=lambda user_id, stored, path: f"{user_id}/{stored}"
        )

        save_patch = mock.patch.object(
            resume_app,
            "save_resume_and_analysis",
            return_value=(1, 2)
        )

        storage_patch.start()
        save_patch.start()

        self.addCleanup(storage_patch.stop)
        self.addCleanup(save_patch.stop)

        with self.client.session_transaction() as session:

            session["user_id"] = 1
            session["user_name"] = "Test User"

    def upload(self, payload, filename, content_type):

        response = self.client.post(
            "/analyze",
            data={
                "target_role": "Software Engineer",
                "resume": (io.BytesIO(payload), filename, content_type),
            },
            headers={"User-Agent": MOBILE_UA},
            follow_redirects=True,
        )

        flashes = FLASH_RE.findall(
            response.get_data(as_text=True)
        )

        return response, [message for _, message in flashes]

    def assert_analyzed(self, response, messages):

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Analysis Result",
            response.get_data(as_text=True)
        )
        self.assertEqual(messages, [])

    # ---------------------------------------------------------
    # Happy paths: mobile multipart variants must all work
    # ---------------------------------------------------------

    def test_pdf_with_octet_stream_mime_is_analyzed(self):

        response, messages = self.upload(
            TEXT_PDF,
            "Abinesh_Resume.pdf",
            "application/octet-stream"
        )

        self.assert_analyzed(response, messages)

    def test_pdf_with_spaces_and_uppercase_extension_is_analyzed(self):

        response, messages = self.upload(
            TEXT_PDF,
            "My Resume (1).PDF",
            "application/pdf"
        )

        self.assert_analyzed(response, messages)

    def test_non_latin_filename_is_accepted(self):

        # secure_filename() used to reduce "<regional>.pdf" to "pdf",
        # after which the extension check rejected a valid upload.
        response, messages = self.upload(
            TEXT_PDF,
            "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd \u0bb0\u0bc6\u0bb8\u0bcd\u0baf\u0bc2\u0bae\u0bcd.pdf",
            "application/pdf"
        )

        self.assert_analyzed(response, messages)

    def test_success_leaves_no_temporary_upload_behind(self):

        before = set(os.listdir(resume_app.UPLOAD_FOLDER))

        response, messages = self.upload(
            TEXT_PDF,
            "Abinesh_Resume.pdf",
            "application/pdf"
        )

        self.assert_analyzed(response, messages)

        after = set(os.listdir(resume_app.UPLOAD_FOLDER))

        self.assertEqual(before, after)

    # ---------------------------------------------------------
    # The reported failure: OCR unavailable on the server
    # ---------------------------------------------------------

    def test_scanned_pdf_without_tesseract_gets_specific_message(self):

        broken_ocr = mock.patch.object(
            resume_app.pytesseract,
            "image_to_string",
            side_effect=resume_app.pytesseract.TesseractNotFoundError()
        )

        with broken_ocr:

            with self.assertLogs(resume_app.logger, level="ERROR") as captured:

                response, messages = self.upload(
                    IMAGE_PDF,
                    "scanned_resume.pdf",
                    "application/pdf"
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("scanned/image PDF" in message for message in messages),
            messages
        )
        self.assertNotIn(
            "Unable to analyze this resume right now.",
            messages
        )

        logged = "\n".join(captured.output)

        self.assertIn("Tesseract", logged)

        # Resume contents must never be written to the log.
        self.assertNotIn("Abinesh", logged)

    def test_scanned_pdf_is_analyzed_when_tesseract_is_available(self):

        try:

            resume_app.pytesseract.get_tesseract_version()

        except Exception:

            self.skipTest("Tesseract OCR is not installed on this machine")

        response, messages = self.upload(
            IMAGE_PDF,
            "scanned_resume.pdf",
            "application/pdf"
        )

        self.assert_analyzed(response, messages)

    # ---------------------------------------------------------
    # Corrupt / empty downloads must get an actionable message
    # ---------------------------------------------------------

    def test_corrupt_pdf_gets_actionable_message(self):

        response, messages = self.upload(
            b"this is not a pdf",
            "resume.pdf",
            "application/pdf"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "could not read this file" in message
                for message in messages
            ),
            messages
        )
        self.assertNotIn(
            "Unable to analyze this resume right now.",
            messages
        )

    def test_empty_file_gets_actionable_message(self):

        response, messages = self.upload(
            b"",
            "resume.pdf",
            "application/pdf"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "could not read this file" in message
                for message in messages
            ),
            messages
        )
        self.assertNotIn(
            "Unable to analyze this resume right now.",
            messages
        )

    def test_corrupt_docx_gets_actionable_message(self):

        response, messages = self.upload(
            b"this is not a docx package",
            "resume.docx",
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                "could not read this file" in message
                for message in messages
            ),
            messages
        )
        self.assertNotIn(
            "Unable to analyze this resume right now.",
            messages
        )

    def test_unsupported_extension_is_rejected(self):

        response, messages = self.upload(
            TEXT_PDF,
            "resume.txt",
            "text/plain"
        )

        self.assertIn(
            "Only PDF and DOCX files are supported.",
            messages
        )


class HelperTests(unittest.TestCase):

    """Small units behind the upload fix."""

    def test_accepted_resume_suffix_uses_the_raw_name(self):

        cases = [
            ("resume.pdf", ".pdf"),
            ("  Resume.PDF  ", ".pdf"),
            ("My Resume (1).docx", ".docx"),
            ("\u0ba4\u0bae\u0bbf\u0bb4\u0bcd.pdf", ".pdf"),
            ("resume.txt", ""),
            ("resume.pdf.exe", ""),
            ("", ""),
            (None, ""),
        ]

        for filename, expected in cases:

            self.assertEqual(
                resume_app.accepted_resume_suffix(filename),
                expected,
                filename
            )

    def test_remove_uploaded_file_never_raises(self):

        resume_app.remove_uploaded_file(
            resume_app.UPLOAD_FOLDER / "never-created.pdf"
        )

        resume_app.remove_uploaded_file(
            resume_app.UPLOAD_FOLDER
        )

    def test_uploaded_size_reports_bytes_and_unknown(self):

        sample = resume_app.UPLOAD_FOLDER / "size-probe.pdf"

        sample.write_bytes(b"12345")

        try:

            self.assertEqual(resume_app.uploaded_size(sample), 5)

        finally:

            sample.unlink(missing_ok=True)

        self.assertEqual(
            resume_app.uploaded_size(
                resume_app.UPLOAD_FOLDER / "never-created.pdf"
            ),
            -1
        )


if __name__ == "__main__":

    unittest.main()


