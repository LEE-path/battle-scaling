"""Acquire evidence without executing it. Standard library; optional PDF reader.

Usage: python sources.py --url https://example.org/work --output ./evidence
       python sources.py --file ./work.pdf --output ./evidence
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import http.client
import importlib
import io
import ipaddress
import json
import mimetypes
from pathlib import Path
import re
import socket
import ssl
import sys
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPHandler, HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener, url2pathname
import uuid

DEFAULT_MAX_BYTES = 2 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
REQUEST_TIMEOUT = 15
MAX_REDIRECTS = 5


def _resolve_public(host: str, port: int) -> list[str]:
    """Reject non-public answers, including mixed public/private DNS records."""
    answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("Only public HTTP(S) hosts are allowed; private, loopback and reserved addresses are refused")
    return addresses


def _validate_url(url: str) -> tuple[str, list[str]]:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError("Only HTTP(S) URL schemes are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are refused")
    if not parsed.hostname or any(ord(char) < 33 for char in url):
        raise ValueError("URL has no valid host or contains control/space characters")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    if port < 1 or port > 65535:
        raise ValueError("Invalid URL port")
    addresses = _resolve_public(parsed.hostname, port)
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, "")), addresses


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_pinned(url: str, addresses: list[str], timeout: float):
    """Pin the validated DNS answer while preserving HTTP Host and TLS SNI."""
    def connect_pinned(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
        last_error = None
        for ip in addresses:
            try:
                return socket.create_connection((ip, address[1]), timeout, source_address)
            except OSError as error:
                last_error = error
        raise last_error or OSError("No validated address available")

    class PinnedHTTP(http.client.HTTPConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._create_connection = connect_pinned

    class PinnedHTTPS(http.client.HTTPSConnection):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._create_connection = connect_pinned

    class PinnedHTTPHandler(HTTPHandler):
        def http_open(self, req):
            return self.do_open(PinnedHTTP, req)

    class PinnedHTTPSHandler(HTTPSHandler):
        def https_open(self, req):
            return self.do_open(PinnedHTTPS, req, context=ssl.create_default_context())

    opener = build_opener(ProxyHandler({}), _NoRedirect(), PinnedHTTPHandler(), PinnedHTTPSHandler())
    request = Request(url, headers={"User-Agent": "BattleScalingEvidence/1.0", "Accept-Encoding": "identity"})
    try:
        return opener.open(request, timeout=timeout)
    except HTTPError as error:
        # HTTP errors still carry a response body worth retaining as evidence
        # of a blocked/error acquisition, never as the requested original work.
        return error


class _ArticleParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template"}
    CHROME = {"nav", "header", "footer", "aside"}
    BREAKS = {"p", "div", "section", "article", "main", "h1", "h2", "h3", "h4", "li", "br", "tr", "blockquote"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.parts: list[str] = []
        self.article: list[str] = []
        self.title: list[str] = []
        self.password = False
        self.captcha_widget = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input" and values.get("type", "").lower() == "password":
            self.password = True
        if "data-sitekey" in values or (tag == "iframe" and any(word in values.get("src", "").lower() for word in ("recaptcha", "hcaptcha"))):
            self.captcha_widget = True
        if tag in self.BREAKS:
            self._append("\n")
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            index = len(self.stack) - 1 - self.stack[::-1].index(tag)
            self.stack = self.stack[:index]
        if tag in self.BREAKS:
            self._append("\n")

    def _append(self, text):
        if any(tag in self.SKIP for tag in self.stack):
            return
        if "title" in self.stack:
            self.title.append(text)
            return
        if "head" in self.stack or any(tag in self.CHROME for tag in self.stack):
            return
        self.parts.append(text)
        if "main" in self.stack or "article" in self.stack:
            self.article.append(text)

    def handle_data(self, data):
        self._append(data)

    @staticmethod
    def clean(parts):
        return "\n".join(line for line in (re.sub(r"[\t \r\f\v]+", " ", item).strip() for item in "".join(parts).split("\n")) if line)

    def text(self):
        return self.clean(self.article if self.clean(self.article) else self.parts)


def _extract_pdf(raw: bytes) -> dict[str, Any]:
    attempt_errors = []
    unavailable = []
    available = []
    for name in ("pypdf", "PyPDF2", "fitz"):
        try:
            library = importlib.import_module(name)
        except ImportError as error:
            unavailable.append({"engine": name, "error": f"{type(error).__name__}: {error}"})
            continue
        except Exception as error:
            attempt_errors.append({"engine": name, "stage": "import", "error": f"{type(error).__name__}: {error}"})
            continue
        available.append(name)
        try:
            if name == "fitz":
                document = library.open(stream=raw, filetype="pdf")
                try:
                    if getattr(document, "needs_pass", False) and not document.authenticate(""):
                        raise ValueError("PDF is encrypted; provide an authorized readable copy")
                    pages = [(page.get_text("text") or "") for page in document]
                finally:
                    document.close()
            else:
                reader = library.PdfReader(io.BytesIO(raw))
                if reader.is_encrypted and not reader.decrypt(""):
                    raise ValueError("PDF is encrypted; provide an authorized readable copy")
                pages = [(page.extract_text() or "") for page in reader.pages]
            if not any(page.strip() for page in pages):
                attempt_errors.append({"engine": name, "stage": "extract", "error": "No extractable text; OCR/host_vision may be required"})
                continue
            text = "\n\n".join(f"[PDF page {index + 1}]\n{page}" for index, page in enumerate(pages))
            warnings = ["PDF text order and printed page numbers require visual verification"]
            warnings.extend(f"PDF reader {item['engine']} failed ({item['stage']}): {item['error']}" for item in attempt_errors)
            return {"text": text, "engine": name, "needs": [], "warnings": warnings,
                    "page_count": len(pages), "attempt_errors": attempt_errors, "unavailable_readers": unavailable}
        except Exception as error:
            attempt_errors.append({"engine": name, "stage": "extract", "error": f"{type(error).__name__}: {error}"})
    if not available and not attempt_errors:
        needs = ["No installed pypdf/PyPDF2/fitz reader; original retained. Supply a host PDF extractor or OCR; no library was installed"]
    else:
        needs = ["All available PDF readers failed or found no text; original retained. Supply an authorized readable PDF or OCR/host_vision with visual page verification"]
    return {"text": "", "engine": None, "needs": needs,
            "warnings": [f"PDF reader {item['engine']} failed ({item['stage']}): {item['error']}" for item in attempt_errors],
            "attempt_errors": attempt_errors, "unavailable_readers": unavailable}


def _local_path(source: str) -> Path | None:
    if re.match(r"^[A-Za-z]:[\\/]", source) or not urlsplit(source).scheme:
        return Path(source)
    parsed = urlsplit(source)
    if parsed.scheme.lower() == "file":
        if parsed.netloc not in ("", "localhost"):
            raise ValueError("Only local file URLs are supported; network shares are refused")
        return Path(url2pathname(parsed.path))
    return None


def fetch_source(url: str | Path, output_dir: str | Path, max_bytes: int = DEFAULT_MAX_BYTES) -> dict[str, Any]:
    """Read a public URL or an explicit local file and save a bounded evidence bundle.

    status: ok / partial / blocked / needs_extractor / error. ``ok`` means
    acquisition succeeded, not that authorship, claims, or completeness are proven.
    The SHA256 covers exactly raw bytes saved, including a truncated prefix.
    """
    original = str(url)
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    stem = "source-" + hashlib.sha256(original.encode("utf-8")).hexdigest()[:12] + "-" + uuid.uuid4().hex[:8]
    paths = {"raw": str(out / (stem + ".raw")), "text": str(out / (stem + ".txt")), "metadata": str(out / (stem + ".json"))}
    result: dict[str, Any] = {"schema_version": 1, "status": "error", "original_url": original, "final_url": original,
        "http_status": None, "accessed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "content_type": None, "bytes_saved": 0, "truncated": False, "sha256": None, "paths": paths,
        "needs": [], "errors": [], "warnings": [], "extraction": {"engine": None}, "redirects": []}
    raw = None
    text = ""
    try:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 1 <= max_bytes <= MAX_DOWNLOAD_BYTES:
            raise ValueError(f"max_bytes must be an integer from 1 to {MAX_DOWNLOAD_BYTES}")
        local = _local_path(original)
        charset = "utf-8"
        if local is not None:
            if str(local).startswith(("\\\\", "//")):
                raise ValueError("Network-share paths are refused; provide a local file")
            local = local.expanduser().resolve(strict=True)
            if not local.is_file():
                raise ValueError("Local source must be a regular file")
            with local.open("rb") as stream:
                raw = stream.read(max_bytes + 1)
            result["content_type"] = mimetypes.guess_type(str(local))[0] or "application/octet-stream"
            result["final_url"] = local.as_uri()
            result["source_kind"] = "local_file"
        else:
            current = original
            deadline = time.monotonic() + REQUEST_TIMEOUT
            for redirect_count in range(MAX_REDIRECTS + 1):
                current, addresses = _validate_url(current)
                result["final_url"] = current
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Request deadline exceeded")
                with _open_pinned(current, addresses, remaining) as response:
                    status = response.code
                    result["http_status"] = status
                    if status in (301, 302, 303, 307, 308):
                        target = response.headers.get("Location")
                        if not target:
                            raise ValueError("Redirect response has no Location")
                        if redirect_count >= MAX_REDIRECTS:
                            raise ValueError("Maximum redirect count exceeded")
                        next_url = urljoin(current, target)
                        # Validate before following any redirect, not only the first URL.
                        _validate_url(next_url)
                        result["redirects"].append({"from": current, "to": next_url, "http_status": status})
                        current = next_url
                        continue
                    result["content_type"] = response.headers.get_content_type()
                    charset = response.headers.get_content_charset() or "utf-8"
                    result["content_encoding"] = response.headers.get("Content-Encoding", "identity")
                    raw = response.read(max_bytes + 1)
                    break
            result["source_kind"] = "http"
        result["truncated"] = len(raw) > max_bytes
        raw = raw[:max_bytes]
        result["bytes_saved"] = len(raw)
        result["sha256"] = hashlib.sha256(raw).hexdigest()
        result["status"] = "partial" if result["truncated"] else "ok"
        if result["truncated"]:
            result["needs"].append("Source exceeded max_bytes; bundle contains only a prefix. Re-fetch with an explicit larger permitted limit")
        if result["http_status"] == 206:
            result["status"] = "partial"
            result["needs"].append("Server returned HTTP 206 Partial Content; this response is not a complete source")
        if result.get("content_encoding", "identity").lower() not in ("identity", ""):
            result["status"] = "needs_extractor" if not result["truncated"] else "partial"
            result["needs"].append("Unexpected encoded response retained without decompression; obtain an unencoded source")
        elif raw.startswith(b"%PDF-") or result["content_type"] == "application/pdf":
            if result["truncated"]:
                result["needs"].append("Incomplete PDF was not parsed")
            else:
                extracted = _extract_pdf(raw)
                text = extracted.pop("text")
                result["needs"].extend(extracted.pop("needs"))
                result["warnings"].extend(extracted.pop("warnings"))
                result["extraction"] = extracted
                if result["needs"]:
                    result["status"] = "needs_extractor"
        elif result["content_type"].startswith("text/") or result["content_type"] in ("application/xhtml+xml", "application/json", "application/xml"):
            try:
                decoded = raw.decode(charset, errors="replace")
            except LookupError:
                decoded = raw.decode("utf-8", errors="replace")
                result["warnings"].append(f"Unknown charset {charset!r}; UTF-8 replacement decoding used")
            if "\ufffd" in decoded:
                result["warnings"].append("Replacement characters occurred; verify source encoding")
            if "html" in result["content_type"]:
                parser = _ArticleParser()
                parser.feed(decoded)
                text = parser.text()
                title = parser.clean(parser.title)
                result["extraction"] = {"engine": "HTMLParser", "title": title}
                title_block = re.search(r"captcha|access denied|attention required|just a moment|verify.{0,15}human|^(sign in|log in|login)(\b|$)|验证码|驗證碼|安全验证|安全驗證|访问验证|訪問驗證|人机验证|人機驗證|访问受限|訪問受限|^\s*(登录|登入|登錄)(\b|[_\s-]|$)", title, re.I)
                challenge = re.search(r"verify (you are|that you are) (a )?human|cf-chl-|challenge-platform|请完成.{0,12}验证|請完成.{0,12}驗證|人机验证|人機驗證", decoded, re.I)
                if parser.password or title_block or (parser.captcha_widget and challenge):
                    result["status"] = "blocked"
                    result["needs"].append("Login/access challenge/CAPTCHA detected; obtain an authorized original copy. Do not substitute search snippets")
            else:
                text = decoded
                result["extraction"] = {"engine": "plain_text", "charset": charset}
        else:
            result["status"] = "needs_extractor" if not result["truncated"] else "partial"
            result["needs"].append("Binary source retained; use a matching host extractor/host_vision and verify against original")
        if result["http_status"] in (401, 403, 407, 429):
            result["status"] = "blocked"
            result["needs"].append(f"HTTP {result['http_status']} blocks original-source access; do not treat this response as the work")
        elif result["http_status"] is not None and result["http_status"] >= 400:
            result["status"] = "error"
            result["errors"].append(f"HTTP {result['http_status']}; retained response is an error page")
        elif result["http_status"] == 206 and result["status"] != "blocked":
            result["status"] = "partial"
    except Exception as error:
        result["status"] = "error"
        result["errors"].append(f"{type(error).__name__}: {error}")
    if raw is not None:
        Path(paths["raw"]).write_bytes(raw)
    else:
        result["paths"]["raw"] = None
    Path(paths["text"]).write_text(text, encoding="utf-8")
    Path(paths["metadata"]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def fetch_and_record(url, output_dir, max_bytes=DEFAULT_MAX_BYTES, *, site_db=None):
    """CLI acquisition boundary: retain result and append the actual HTTP receipt."""
    result=fetch_source(url,output_dir,max_bytes)
    try:
        from site_registry import record_fetch
        result['site_experience']=record_fetch(result,db=site_db)
    except Exception as error:
        result['site_experience']={'status':'error','error':f'{type(error).__name__}: {error}'}
        result.setdefault('warnings',[]).append('Site registry update failed; source result retained: '+str(error))
    metadata=result.get('paths',{}).get('metadata')
    if metadata:
        Path(metadata).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url")
    group.add_argument("--file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)
    result = fetch_and_record(args.url if args.url is not None else args.file, args.output, args.max_bytes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
