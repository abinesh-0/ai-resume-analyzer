"""Regression tests for the stuck "Analyzing your resume..." spinner.

The analyze form submits as a normal navigation. While that POST is in
flight the browser keeps showing the index page with a disabled button, and
the inline script used to leave #analyzeBtn stuck on "Analyzing your
resume..." forever whenever the response was slow (Render cold start, OCR
of a scanned PDF) or never arrived (dropped mobile connection, proxy
timeout) - the report behind this fix. Page script keeps running during a
pending navigation, so templates/index.html now ships a staged watchdog
(20 s informational notice, 75 s button restore + retry message) and a
`pageshow` reset for back/forward restores.

Run with:

    python -m unittest discover -s tests -v

Nothing here touches Supabase: the app is imported with unreachable
connection URLs (same guard as the other suites) and the only route used
here stubs its database read.
"""

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

import app as resume_app

INDEX_TEMPLATE = os.path.join(
    resume_app.app.root_path,
    "templates",
    "index.html",
)

with open(INDEX_TEMPLATE, encoding="utf-8") as handle:
    INDEX_HTML = handle.read()

DOCKERFILE = os.path.join(
    resume_app.app.root_path,
    "Dockerfile",
)


def default_ms(constant):
    """The numeric default of a `const ... = <number>;` in the template."""

    match = re.search(
        rf"{constant}\s*=\s*(\d+)",
        INDEX_HTML,
    )
    return int(match.group(1)) if match else None


class AnalyzeSpinnerWatchdogTemplateTests(unittest.TestCase):

    """Static guarantees on the inline watchdog in templates/index.html."""

    def test_submit_handler_still_shows_spinner_state(self):

        # The loading UX itself must not regress: guard, dataset flag,
        # disabled button and the spinner label.
        self.assertIn(
            "analyzeBtn.dataset.loading ===",
            INDEX_HTML,
        )
        self.assertIn("Analyzing your resume...", INDEX_HTML)

    def test_notice_element_and_css_exist(self):

        self.assertIn('id="analyzeNotice"', INDEX_HTML)
        self.assertIn('aria-live="polite"', INDEX_HTML)
        self.assertIn(".analyze-notice[hidden]", INDEX_HTML)

    def test_stage_one_notice_default(self):

        self.assertEqual(
            default_ms("ANALYZE_NOTICE_MS_DEFAULT"),
            20000,
        )
        self.assertIn("Still analyzing", INDEX_HTML)

    def test_stage_two_retry_default_and_button_restore(self):

        self.assertEqual(
            default_ms("ANALYZE_RETRY_MS_DEFAULT"),
            75000,
        )
        # The retry stage must hand the button back to the user.
        self.assertRegex(
            INDEX_HTML,
            r"analyzeRetryTimer\s*=\s*setTimeout\(\s*"
            r"function\s*\(\)\s*\{\s*resetAnalyzeBtn\(\);",
        )
        self.assertIn("taking longer than usual", INDEX_HTML)

    def test_watchdog_defaults_stay_below_gunicorn_timeout(self):

        # Dockerfile runs gunicorn with --timeout 120; the client must give
        # up (and offer a retry) before the server is killed mid-request.
        with open(DOCKERFILE, encoding="utf-8") as handle:
            dockerfile = handle.read()

        match = re.search(r"--timeout\s+(\d+)", dockerfile)
        self.assertIsNotNone(match, "gunicorn --timeout missing")
        gunicorn_seconds = int(match.group(1))

        notice = default_ms("ANALYZE_NOTICE_MS_DEFAULT")
        retry = default_ms("ANALYZE_RETRY_MS_DEFAULT")

        self.assertLess(notice, retry)
        self.assertLess(retry, gunicorn_seconds * 1000)

    def test_timeout_overrides_exist_for_browser_tests(self):

        # The browser harness shrinks these windows via window.* before
        # clicking Analyze; the submit handler must read them at submit time.
        self.assertIn("window.ANALYZE_NOTICE_MS", INDEX_HTML)
        self.assertIn("window.ANALYZE_RETRY_MS", INDEX_HTML)

    def test_pageshow_resets_a_restored_stuck_button(self):

        match = re.search(
            r'window\.addEventListener\(\s*"pageshow"',
            INDEX_HTML,
        )
        self.assertIsNotNone(match)

        tail = INDEX_HTML[match.start():match.start() + 600]
        self.assertIn("resetAnalyzeBtn()", tail)

    def test_button_reset_restores_idle_state(self):

        self.assertIn("analyzeBtnIdleHtml", INDEX_HTML)
        self.assertRegex(
            INDEX_HTML,
            r"const resetAnalyzeBtn\s*=\s*function\s*\(\)\s*\{",
        )


class AnalyzeSpinnerRenderedPageTests(unittest.TestCase):

    """The watchdog must actually reach the browser via the rendered page."""

    @classmethod
    def setUpClass(cls):

        cls.client = resume_app.app.test_client()

    def test_home_page_ships_watchdog_markup_and_script(self):

        with mock.patch.object(
            resume_app,
            "get_user_resumes",
            return_value=[],
        ):
            with self.client.session_transaction() as session:
                session["user_id"] = 1

            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('id="analyzeNotice"', html)
        self.assertIn("pageshow", html)
        self.assertIn("ANALYZE_RETRY_MS_DEFAULT", html)
        self.assertIn("resetAnalyzeBtn", html)

    def test_home_page_without_login_redirects_to_login(self):

        # Sanity: the new markup only appears behind the session check.
        # A fresh client keeps this test independent of the session that
        # other tests in this class may have set on the shared client.
        guest = resume_app.app.test_client()
        response = guest.get("/")
        self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    unittest.main()
