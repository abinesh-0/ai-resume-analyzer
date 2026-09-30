"""Deployment contract tests.

The production image must ship Tesseract OCR (with the English language
data) because Render's native Python runtime does not provide it, and it
must run Gunicorn on Render's assigned PORT. These tests pin that
contract, plus the pytesseract configuration helpers, so a future change
cannot silently break scanned-PDF analysis in production.

Run with:

    python -m unittest discover -s tests -v
"""

import pathlib
import unittest

import app as resume_app

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "Dockerfile"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
REQUIREMENTS = REPO_ROOT / "requirements.txt"


class DockerfileContractTests(unittest.TestCase):

    """The image must ship the OCR stack and Render's port contract."""

    @classmethod
    def setUpClass(cls):

        if not DOCKERFILE.exists():

            raise unittest.SkipTest("Dockerfile is not present")

        cls.text = DOCKERFILE.read_text(encoding="utf-8")

    def test_installs_tesseract_with_english_language_data(self):

        self.assertIn("tesseract-ocr", self.text)
        self.assertIn("tesseract-ocr-eng", self.text)

    def test_verifies_ocr_at_build_time(self):

        self.assertIn("get_tesseract_version", self.text)
        self.assertIn("get_languages", self.text)

    def test_installs_python_requirements(self):

        self.assertIn("requirements.txt", self.text)
        self.assertIn("pip install -r requirements.txt", self.text)

    def test_runs_gunicorn_on_render_port(self):

        self.assertIn("gunicorn app:app", self.text)
        self.assertIn("0.0.0.0", self.text)
        self.assertIn("${PORT", self.text)
        self.assertIn("exec ", self.text)

    def test_exposes_the_documented_port(self):

        self.assertIn("EXPOSE 10000", self.text)

    def test_cmd_is_valid_json_and_runs_gunicorn(self):

        import json

        cmd_lines = [
            line
            for line in self.text.splitlines()
            if line.startswith("CMD ")
        ]

        self.assertEqual(len(cmd_lines), 1)

        command = json.loads(cmd_lines[0][len("CMD "):])

        self.assertEqual(command[0], "sh")
        self.assertIn("gunicorn app:app", command[-1])

    def test_hardcodes_no_credentials(self):

        for marker in ("SECRET_KEY=", "MAIL_PASSWORD=", "SERVICE_ROLE_KEY="):

            self.assertNotIn(marker, self.text)


class DockerignoreContractTests(unittest.TestCase):

    """Local secrets and runtime data must stay out of the image."""

    @classmethod
    def setUpClass(cls):

        if not DOCKERIGNORE.exists():

            raise unittest.SkipTest(".dockerignore is not present")

        cls.lines = [
            line.strip()
            for line in DOCKERIGNORE.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def test_env_files_are_excluded(self):

        self.assertIn(".env", self.lines)
        self.assertIn(".env.*", self.lines)
        self.assertIn("!.env.example", self.lines)

    def test_local_environments_and_uploads_are_excluded(self):

        self.assertIn("venv/", self.lines)
        self.assertIn("uploads/*", self.lines)
        self.assertIn("!uploads/.gitkeep", self.lines)


class TesseractConfigurationTests(unittest.TestCase):

    """pytesseract must be able to find the installed binary."""

    def test_configure_tesseract_defaults_to_path_lookup(self):

        original = resume_app.pytesseract.pytesseract.tesseract_cmd

        try:

            self.assertEqual(
                resume_app.configure_tesseract(""),
                "tesseract"
            )

            self.assertEqual(
                resume_app.pytesseract.pytesseract.tesseract_cmd,
                "tesseract"
            )

        finally:

            resume_app.pytesseract.pytesseract.tesseract_cmd = original

    def test_configure_tesseract_applies_an_explicit_command(self):

        original = resume_app.pytesseract.pytesseract.tesseract_cmd

        try:

            self.assertEqual(
                resume_app.configure_tesseract("  /usr/bin/tesseract  "),
                "/usr/bin/tesseract"
            )

            self.assertEqual(
                resume_app.pytesseract.pytesseract.tesseract_cmd,
                "/usr/bin/tesseract"
            )

        finally:

            resume_app.pytesseract.pytesseract.tesseract_cmd = original

    def test_ocr_status_never_raises(self):

        status = resume_app.ocr_status()

        self.assertIsInstance(status, str)
        self.assertTrue(status.strip())

        # Locally (Tesseract installed) it names the version; on a bare
        # machine it degrades to "unavailable (<ExceptionType>)".
        if "unavailable" not in status:

            self.assertIn("Tesseract", status)


class RequirementsContractTests(unittest.TestCase):

    def test_gunicorn_is_still_a_dependency(self):

        text = REQUIREMENTS.read_text(encoding="utf-8").lower()

        self.assertIn("gunicorn", text)


if __name__ == "__main__":

    unittest.main()

