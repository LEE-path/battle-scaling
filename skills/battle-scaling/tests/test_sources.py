"""Source acquisition tests use local fixtures, never an external website."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sources


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/article")
            self.end_headers()
            return
        if self.path == "/private-redirect":
            self.send_response(302)
            self.send_header("Location", "file:///etc/passwd")
            self.end_headers()
            return
        if self.path == "/private-http-redirect":
            self.send_response(302)
            self.send_header("Location", "http://10.0.0.1/work")
            self.end_headers()
            return
        if self.path == "/loop":
            self.send_response(302)
            self.send_header("Location", "/loop")
            self.end_headers()
            return
        if self.path == "/403":
            self.send_response(403)
            body = b"<title>Forbidden</title><body>Access denied</body>"
        elif self.path == "/login":
            self.send_response(200)
            body = b'<title>Sign in</title><form><input type="password"></form>'
        elif self.path == "/captcha":
            self.send_response(200)
            body = b"<title>Just a moment...</title><body>Verify you are human</body>"
        elif self.path == "/captcha-zh":
            self.send_response(200)
            body = '<title>验证码_哔哩哔哩</title><body>请完成安全验证</body>'.encode("utf-8")
            body += b" " * (1374 - len(body))
        elif self.path == "/large":
            self.send_response(200)
            body = b"a" * 4096
        elif self.path == "/broken":
            self.send_response(500)
            body = b"server error"
        elif self.path == "/206":
            self.send_response(206)
            body = b"only part of the original"
        else:
            self.send_response(200)
            body = ('<html><head><title>Original work</title><script>evil()</script></head>'
                    '<body><nav>Navigation</nav><main><h1>Evidence</h1>'
                    '<p>Original passage 中文 &amp; context.</p></main>'
                    '<footer>Footer</footer></body></html>').encode("utf-8")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def fetch(self, path, **kwargs):
        # Production refuses loopback. This single resolver substitution is
        # confined to tests so the real HTTP machinery can use local fixtures.
        with patch.object(sources, "_resolve_public", return_value=["127.0.0.1"]):
            return sources.fetch_source(self.base + path, self.out, **kwargs)

    def test_body_hash_and_output_confinement(self):
        result = self.fetch("/article")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["http_status"], 200)
        text = Path(result["paths"]["text"]).read_text(encoding="utf-8")
        self.assertIn("Original passage 中文 & context.", text)
        self.assertNotIn("evil()", text)
        self.assertNotIn("Navigation", text)
        self.assertNotIn("Footer", text)
        import hashlib
        raw = Path(result["paths"]["raw"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result["sha256"])
        self.assertTrue(result["accessed_at"].endswith("Z"))
        for name in result["paths"].values():
            self.assertTrue(Path(name).resolve().is_relative_to(self.out.resolve()))
        saved = json.loads(Path(result["paths"]["metadata"]).read_text(encoding="utf-8"))
        self.assertEqual(saved["sha256"], result["sha256"])

    def test_redirect_records_final_url(self):
        result = self.fetch("/redirect")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["original_url"], self.base + "/redirect")
        self.assertEqual(result["final_url"], self.base + "/article")

    def test_redirect_target_is_validated(self):
        result = self.fetch("/private-redirect")
        self.assertEqual(result["status"], "error")
        self.assertIn("scheme", " ".join(result["errors"]).lower())

    def test_redirect_to_private_http_is_refused_before_connection(self):
        def resolve(host, port):
            if host == "127.0.0.1":
                return [host]
            raise ValueError("private redirect rejected")
        with patch.object(sources, "_resolve_public", side_effect=resolve):
            result = sources.fetch_source(self.base + "/private-http-redirect", self.out)
        self.assertEqual(result["status"], "error")
        self.assertIn("private redirect rejected", " ".join(result["errors"]))

    def test_redirect_loop_is_bounded(self):
        result = self.fetch("/loop")
        self.assertEqual(result["status"], "error")
        self.assertIn("redirect", " ".join(result["errors"]).lower())

    def test_403_and_login_and_captcha_are_blocked(self):
        for path in ("/403", "/login", "/captcha"):
            with self.subTest(path=path):
                result = self.fetch(path)
                self.assertEqual(result["status"], "blocked")
                self.assertTrue(result["needs"])
                self.assertTrue(Path(result["paths"]["raw"]).exists())

    def test_chinese_bilibili_captcha_with_http_200_is_blocked(self):
        result = self.fetch("/captcha-zh")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["bytes_saved"], 1374)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("验证码_哔哩哔哩", result["extraction"]["title"])

    def test_truncation_is_visible_and_hashed(self):
        result = self.fetch("/large", max_bytes=128)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["truncated"])
        self.assertEqual(result["bytes_saved"], 128)
        self.assertEqual(Path(result["paths"]["raw"]).stat().st_size, 128)

    def test_http_error_is_not_source_success(self):
        result = self.fetch("/broken")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["http_status"], 500)

    def test_server_partial_content_is_not_complete_source(self):
        result = self.fetch("/206")
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["truncated"])
        self.assertTrue(any("206" in value for value in result["needs"]))

    def test_private_network_and_unsupported_scheme_are_refused(self):
        for url in ("http://127.0.0.1/", "http://169.254.169.254/", "ftp://example.com/a", "http://user:pass@example.com/"):
            with self.subTest(url=url):
                result = sources.fetch_source(url, self.out)
                self.assertEqual(result["status"], "error")
                self.assertTrue(result["errors"])

    def test_local_file_and_local_truncation(self):
        path = Path(self.tmp.name) / "input.txt"
        path.write_text("local evidence", encoding="utf-8")
        result = sources.fetch_source(path, self.out)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(Path(result["paths"]["text"]).read_text(encoding="utf-8"), "local evidence")
        self.assertEqual(sources.fetch_source(path, self.out, max_bytes=4)["status"], "partial")

    def test_pdf_without_installed_extractor_preserves_original(self):
        path = Path(self.tmp.name) / "fixture.pdf"
        path.write_bytes(b"%PDF-1.4\nminimal fixture, intentionally not parsed\n%%EOF")
        original_import = importlib.import_module

        def no_pdf(name, *args, **kwargs):
            if name in ("pypdf", "PyPDF2", "fitz"):
                raise ImportError("test: PDF extractor unavailable")
            return original_import(name, *args, **kwargs)

        with patch.object(sources.importlib, "import_module", side_effect=no_pdf):
            result = sources.fetch_source(path, self.out)
        self.assertEqual(result["status"], "needs_extractor")
        self.assertTrue(result["needs"])
        self.assertEqual(Path(result["paths"]["raw"]).read_bytes(), path.read_bytes())

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "optional installed fitz fixture")
    def test_pdf_uses_installed_fitz_and_preserves_page_order(self):
        fitz = importlib.import_module("fitz")
        document = fitz.open()
        for text in ("Page one original evidence", "Page two original evidence"):
            document.new_page().insert_text((72, 72), text)
        path = Path(self.tmp.name) / "two-pages.pdf"
        path.write_bytes(document.tobytes())
        document.close()
        original_import = importlib.import_module

        def fitz_only(name, *args, **kwargs):
            if name in ("pypdf", "PyPDF2"):
                raise ImportError("test: only fitz is installed")
            return original_import(name, *args, **kwargs)

        with patch.object(sources.importlib, "import_module", side_effect=fitz_only):
            result = sources.fetch_source(path, self.out)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["extraction"]["engine"], "fitz")
        self.assertEqual(result["extraction"]["page_count"], 2)
        text = Path(result["paths"]["text"]).read_text(encoding="utf-8")
        self.assertIn("[PDF page 1]", text)
        self.assertIn("[PDF page 2]", text)
        self.assertLess(text.index("Page one"), text.index("Page two"))
        self.assertTrue(any("visual verification" in warning for warning in result["warnings"]))

    def test_failed_pdf_readers_try_later_library_and_log_errors(self):
        path = Path(self.tmp.name) / "fixture.pdf"
        path.write_bytes(b"%PDF-1.4\nfixture for mocked parser sequence\n%%EOF")

        def broken_reader(*args, **kwargs):
            raise ValueError("fixture parser failure")

        class Document:
            needs_pass = False

            def __iter__(self):
                return iter([SimpleNamespace(get_text=lambda mode: "fitz recovered evidence")])

            def close(self):
                pass

        def libraries(name):
            if name in ("pypdf", "PyPDF2"):
                return SimpleNamespace(PdfReader=broken_reader)
            if name == "fitz":
                return SimpleNamespace(open=lambda **kwargs: Document())
            raise ImportError(name)

        with patch.object(sources.importlib, "import_module", side_effect=libraries):
            result = sources.fetch_source(path, self.out)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["extraction"]["engine"], "fitz")
        self.assertEqual(len(result["extraction"]["attempt_errors"]), 2)
        self.assertTrue(any("fixture parser failure" in warning for warning in result["warnings"]))

    def test_all_available_pdf_readers_fail_with_retained_error_log(self):
        path = Path(self.tmp.name) / "fixture.pdf"
        path.write_bytes(b"%PDF-1.4\ninvalid fixture\n%%EOF")

        def broken(*args, **kwargs):
            raise ValueError("all parsers rejected fixture")

        def libraries(name):
            if name in ("pypdf", "PyPDF2"):
                return SimpleNamespace(PdfReader=broken)
            if name == "fitz":
                return SimpleNamespace(open=broken)
            raise ImportError(name)

        with patch.object(sources.importlib, "import_module", side_effect=libraries):
            result = sources.fetch_source(path, self.out)
        self.assertEqual(result["status"], "needs_extractor")
        self.assertEqual(len(result["extraction"]["attempt_errors"]), 3)
        self.assertTrue(result["needs"])
        self.assertEqual(Path(result["paths"]["raw"]).read_bytes(), path.read_bytes())

    def test_invalid_limit_and_missing_file_are_structured_errors(self):
        for value in (0, -1, sources.MAX_DOWNLOAD_BYTES + 1):
            self.assertEqual(sources.fetch_source("missing.txt", self.out, max_bytes=value)["status"], "error")
        self.assertEqual(sources.fetch_source(Path(self.tmp.name) / "missing.txt", self.out)["status"], "error")

    def test_timeout_returns_structured_error(self):
        with patch.object(sources, "_resolve_public", return_value=["127.0.0.1"]), patch.object(sources, "_open_pinned", side_effect=TimeoutError("fixture timeout")):
            result = sources.fetch_source(self.base + "/article", self.out)
        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", " ".join(result["errors"]))
        self.assertIsNone(result["paths"]["raw"])
        self.assertTrue(Path(result["paths"]["metadata"]).is_file())


if __name__ == "__main__":
    unittest.main()
