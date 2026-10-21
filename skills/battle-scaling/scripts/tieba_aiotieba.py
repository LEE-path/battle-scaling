"""One anonymous, read-only aiotieba page request per JSON stdin message.

Run this worker with a Python environment containing aiotieba. It intentionally
does not load browser cookies, account files, or credentials. The caller owns
pagination, throttling, persistence and completeness checks. stdout is exactly
one JSON line; SDK diagnostics are redirected to stderr.
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import importlib.metadata
import json
import logging
import math
import re
import sys
from typing import Any
from urllib.parse import quote, urlencode

SCHEMA_VERSION = "1.0"
BACKEND = "aiotieba"
DEFAULT_FORUM = "汪峰在"
_ALLOWED = {
    "op", "forum", "query", "tid", "pid", "pn", "rn", "timeout",
    "only_thread", "is_good", "only_thread_author",
}
_ENDPOINTS = {
    "forum": "/c/f/frs/page?cmd=301001",
    "search": "/c/s/searchpost",
    "thread": "/c/f/pb/page?cmd=302001",
    "comments": "/c/f/pb/floor?cmd=302002",
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _integer(value: Any, name: str, low: int = 1, high: int = 2**63 - 1) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise ValueError(f"{name} must be a positive integer")
    result = int(value)
    if not low <= result <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")
    return result


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a JSON boolean")
    return value


def validate_request(raw: Any) -> dict[str, Any]:
    """Validate before importing the SDK or opening a network connection."""
    if not isinstance(raw, dict):
        raise ValueError("stdin must contain a JSON object")
    if set(raw) - _ALLOWED:
        # Do not echo unknown fields: they may accidentally contain credentials.
        raise ValueError("unsupported input fields; credentials are not accepted")
    op = raw.get("op")
    if op not in _ENDPOINTS:
        raise ValueError("op must be forum, search, thread or comments")
    result: dict[str, Any] = {
        "op": op,
        "pn": _integer(raw.get("pn", 1), "pn", high=100000),
    }
    timeout = raw.get("timeout", 20)
    if isinstance(timeout, bool):
        raise ValueError("timeout must be a finite number in [1, 60]")
    try:
        timeout = float(timeout)
    except (TypeError, ValueError):
        raise ValueError("timeout must be a finite number in [1, 60]") from None
    if not math.isfinite(timeout) or not 1 <= timeout <= 60:
        raise ValueError("timeout must be a finite number in [1, 60]")
    result["timeout"] = timeout
    if op in ("forum", "search"):
        forum = raw.get("forum", DEFAULT_FORUM)
        if not isinstance(forum, str) or not forum.strip() or len(forum) > 80:
            raise ValueError("forum must be a non-empty name of at most 80 characters")
        result["forum"] = forum.strip()
    if op in ("forum", "search", "thread"):
        low, high = {"forum": (1, 100), "search": (1, 50), "thread": (2, 30)}[op]
        result["rn"] = _integer(raw.get("rn", 30), "rn", low, high)
    if op in ("thread", "comments"):
        result["tid"] = str(_integer(raw.get("tid"), "tid"))
    if op == "comments":
        result["pid"] = str(_integer(raw.get("pid"), "pid"))
    if op == "search":
        query = raw.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("query must be non-empty text of at most 500 characters")
        result["query"] = query.strip()
        result["only_thread"] = _boolean(raw.get("only_thread", False), "only_thread")
    if op == "forum":
        result["is_good"] = _boolean(raw.get("is_good", False), "is_good")
    if op == "thread":
        result["only_thread_author"] = _boolean(
            raw.get("only_thread_author", False), "only_thread_author"
        )
    return result


def _id(value: Any) -> str:
    return str(value) if value else ""


def _timestamp(value: Any) -> str | None:
    try:
        seconds = int(value)
        if seconds > 0:
            return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        pass
    return None


def _thread_url(tid: Any, pid: Any = None, pn: Any = None) -> str:
    if not tid:
        return ""
    url = f"https://tieba.baidu.com/p/{quote(str(tid), safe='')}"
    if pid:
        return f"{url}?pid={quote(str(pid), safe='')}#{quote(str(pid), safe='')}"
    return f"{url}?pn={int(pn)}" if pn else url


def _forum_url(name: str) -> str:
    return "https://tieba.baidu.com/f?" + urlencode({"kw": name, "ie": "utf-8"})


def _author(obj: Any) -> dict[str, str]:
    user = getattr(obj, "user", None)
    return {
        "name": str(getattr(user, "show_name", "") or getattr(obj, "show_name", "") or ""),
        "uid": _id(getattr(obj, "author_id", None) or getattr(user, "user_id", None)),
    }


def normalize_images(contents: Any) -> list[dict[str, Any]]:
    """Keep the source URLs and their actual meanings; never fetch image bytes."""
    images = []
    for position, image in enumerate(getattr(contents, "imgs", ()) or ()):
        original = str(getattr(image, "origin_src", "") or "")
        large = str(getattr(image, "big_src", "") or "")
        thumbnail = str(getattr(image, "src", "") or "")
        images.append({
            "index": position,
            "url": original or large or thumbnail,
            "original_url": original,
            "large_url": large,
            "thumbnail_url": thumbnail,
            "hash": str(getattr(image, "hash", "") or ""),
            "display_width": getattr(image, "show_width", None),
            "display_height": getattr(image, "show_height", None),
            "original_size": getattr(image, "origin_size", None),
        })
    return images


def _links(contents: Any) -> list[dict[str, str]]:
    result = []
    for link in getattr(contents, "links", ()) or ():
        result.append({
            "text": str(getattr(link, "text", "") or ""),
            "url": str(getattr(link, "url", "") or getattr(link, "link", "") or ""),
        })
    return result


def normalize_item(obj: Any, kind: str, request: dict[str, Any]) -> dict[str, Any]:
    contents = getattr(obj, "contents", None)
    tid = _id(getattr(obj, "tid", None) or request.get("tid"))
    pid = _id(getattr(obj, "pid", None))
    created = getattr(obj, "create_time", None)
    item = {
        "kind": kind,
        "tid": tid,
        "pid": pid,
        "floor": getattr(obj, "floor", None),
        "title": str(getattr(obj, "title", "") or ""),
        "text": str(getattr(obj, "text", "") or ""),
        "author": _author(obj),
        "created_at": _timestamp(created),
        "created_timestamp": created,
        "reply_num": getattr(obj, "reply_num", None),
        "images": normalize_images(contents),
        "links": _links(contents),
        "forum": {
            "fid": _id(getattr(obj, "fid", None)),
            "name": str(getattr(obj, "fname", "") or request.get("forum", "")),
        },
        "url": _thread_url(tid, pid),
    }
    if kind == "comment":
        item["parent_pid"] = _id(getattr(obj, "ppid", None) or request.get("pid"))
        item["reply_to_uid"] = _id(getattr(obj, "reply_to_id", None))
    if kind in ("post", "comment"):
        item["is_thread_author"] = getattr(obj, "is_thread_author", None)
        # Keep signatures separate so they need not become feat evidence.
        item["signature"] = str(getattr(obj, "sign", "") or "")
        if item["signature"] and contents is not None:
            item["text"] = str(getattr(contents, "text", "") or "")
    if kind == "search_result":
        content_type = getattr(obj, "content_type", None)
        item["content_type"] = getattr(content_type, "name", str(content_type))
        item["parent_pid"] = _id(getattr(obj, "ppid", None))
        item["is_excerpt"] = True
    if kind in ("thread", "thread_summary"):
        item["is_excerpt"] = kind == "thread_summary"
    return item


def normalize_page(obj: Any, request: dict[str, Any]) -> dict[str, Any]:
    page = getattr(obj, "page", None)
    return {
        "requested_page": request["pn"],
        "current_page": getattr(page, "current_page", None),
        "total_page": getattr(page, "total_page", None),
        "has_more": getattr(page, "has_more", None),
        "has_prev": getattr(page, "has_prev", None),
        "page_size": getattr(page, "page_size", None),
        "total_count": getattr(page, "total_count", None),
    }


def _envelope(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("op")
    if op in ("thread", "comments"):
        url = _thread_url(request.get("tid"), pn=request.get("pn"))
    elif op == "search":
        url = "https://tieba.baidu.com/f/search/res?" + urlencode({
            "kw": request.get("forum", ""), "qw": request.get("query", ""),
            "ie": "utf-8", "pn": request.get("pn", 1),
        })
    else:
        url = _forum_url(request.get("forum", DEFAULT_FORUM))
    return {
        "status": "ok", "schema_version": SCHEMA_VERSION, "backend": BACKEND,
        "op": op, "request": request, "page": {}, "forum": {},
        "thread": {}, "items": [],
        "source": {
            "url": url, "api_path": _ENDPOINTS.get(op), "retrieved_at": _now(),
            "captured_at": _now(), "backend": BACKEND,
            "authentication": "anonymous", "request_count": 0,
            "scope": "one_api_page", "images_downloaded": False,
            "read_scope": "SDK decoded one-page snapshot; not raw HTTP response bytes",
            "completeness": "page_only_not_entire_thread_or_forum",
        },
    }


def _safe_error(error: Exception) -> dict[str, Any]:
    message = str(getattr(error, "msg", "") or error)
    message = re.sub(r"(?i)(BDUSS|STOKEN|cookie|authorization)\s*[:=]\s*[^\s,;]+", r"\1=[redacted]", message)
    code = getattr(error, "code", None)
    blocked = code in (401, 403, 429) or bool(re.search(
        r"验证码|安全验证|请完成验证|访问过于频繁|请求过于频繁|限流|captcha|forbidden|too many requests|login required",
        message, re.I,
    ))
    return {
        "type": type(error).__name__, "code": code,
        "message": message[:600] or type(error).__name__,
        "blocked": blocked,
        "action": "stop_and_report_or_request_manual_verification" if blocked else "report_failure_without_claiming_empty_results",
    }


async def run_once(raw: Any, *, client_factory: Any = None) -> dict[str, Any]:
    """Return a normalized response; optional injected factory supports offline tests."""
    request: dict[str, Any] = {}
    try:
        request = validate_request(raw)
        result = _envelope(request)
        if client_factory is None:
            import aiotieba
            from aiotieba.config import TimeoutConfig

            timeout = request["timeout"]
            factory_args = {
                "BDUSS": "", "STOKEN": "", "try_ws": False, "proxy": False,
                "timeout": TimeoutConfig(
                    http_acquire_conn=min(timeout, 5),
                    http_read=timeout, http_connect=min(timeout, 8),
                ),
            }
            client_factory = lambda: aiotieba.Client(**factory_args)
            result["source"]["sdk_version"] = importlib.metadata.version("aiotieba")
        async with asyncio.timeout(request["timeout"]):
            async with client_factory() as client:
                op, pn = request["op"], request["pn"]
                result["source"]["request_count"] = 1
                if op == "forum":
                    data = await client.get_threads(
                        request["forum"], pn=pn, rn=request["rn"], is_good=request["is_good"]
                    )
                    kind = "thread_summary"
                elif op == "search":
                    data = await client.search_in_forum(
                        request["forum"], request["query"], pn=pn, rn=request["rn"],
                        only_thread=request["only_thread"],
                    )
                    kind = "search_result"
                elif op == "thread":
                    data = await client.get_posts(
                        int(request["tid"]), pn=pn, rn=request["rn"],
                        only_thread_author=request["only_thread_author"], with_comments=False,
                    )
                    kind = "post"
                else:
                    data = await client.get_comments(int(request["tid"]), int(request["pid"]), pn=pn)
                    kind = "comment"
                if getattr(data, "err", None) is not None:
                    raise data.err
                result["page"] = normalize_page(data, request)
                forum = getattr(data, "forum", None)
                result["forum"] = {
                    "fid": _id(getattr(forum, "fid", None)),
                    "name": str(getattr(forum, "fname", "") or request.get("forum", "")),
                }
                thread = getattr(data, "thread", None)
                if thread is not None:
                    result["thread"] = normalize_item(thread, "thread", request)
                result["items"] = [normalize_item(item, kind, request) for item in data.objs]
                if op == "comments":
                    post = getattr(data, "post", None)
                    if post is not None:
                        result["parent_post"] = normalize_item(post, "post", request)
                if op == "thread":
                    result["source"]["comments_included"] = False
                    result["source"]["comments_note"] = "Use comments op for every parent pid with reply_num > 0."
        return result
    except Exception as error:
        if "result" not in locals():
            result = _envelope(request)
        result["error"] = _safe_error(error)
        result["status"] = "blocked" if result["error"]["blocked"] else "error"
        if not request:
            result["source"]["request_count"] = 0
        return result


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        raw = json.loads(sys.stdin.read(1024 * 1024))
    except (json.JSONDecodeError, UnicodeError) as error:
        result = _envelope({})
        result.update(status="error", error=_safe_error(ValueError("invalid JSON stdin")))
        result["source"]["request_count"] = 0
    else:
        # SDK versions may use different logger names. Redirection also catches
        # unsolicited import messages without mixing them into the JSON protocol.
        logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
        with contextlib.redirect_stdout(sys.stderr):
            result = asyncio.run(run_once(raw))
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
