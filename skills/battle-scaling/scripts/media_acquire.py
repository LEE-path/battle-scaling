"""Small media-only helpers; does not run character ratings or evidence audits."""
from __future__ import annotations

import argparse
import asyncio
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
MEDIA = re.compile(r"\.(?:jpe?g|png|webp|avif|gif|mp4|webm|m3u8|mpd)(?:\?|$)", re.I)


def headers(referer=None):
    result = {"User-Agent": UA}
    if referer:
        result["Referer"] = referer
    return result


def public_url(value):
    if urlsplit(value).scheme not in ("http", "https"):
        raise ValueError("Expected an HTTP(S) media/page URL")
    return value


def probe(path):
    """Report real decoded dimensions/tracks, not filename or exit status."""
    p = Path(path)
    try:
        from PIL import Image
        with Image.open(p) as im:
            result = {"kind": "image", "format": im.format, "width": im.width, "height": im.height}
            im.verify()
        return result
    except ImportError:
        pass
    except (OSError, ValueError, SyntaxError):
        pass
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", str(p)],
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=True)
    data = json.loads(r.stdout)
    tracks = data.get("streams", [])
    if not any(t.get("codec_type") == "video" and t.get("width", 0) > 0 for t in tracks):
        raise ValueError("No usable video track; this may be an audio-only download")
    return {"kind": "video", **data}


class MediaLinks(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.items = base, {}

    def add(self, value, origin, label=""):
        if not value or value.startswith(("data:", "blob:", "javascript:")):
            return
        value = urljoin(self.base, html.unescape(value))
        if urlsplit(value).scheme not in ("http", "https"):
            return
        kind = "stream" if re.search(r"\.(m3u8|mpd)(?:\?|$)", value, re.I) else (
            "video" if re.search(r"\.(mp4|webm)(?:\?|$)", value, re.I) else "image")
        self.items.setdefault(value, {"url": value, "kind": kind, "found_in": origin,
                                     "label": label, "referer": self.base})

    def handle_starttag(self, tag, pairs):
        a = dict(pairs)
        if tag in ("img", "source", "video"):
            for key in ("src", "data-src", "data-original", "data-lazy-src", "poster"):
                self.add(a.get(key), f"{tag}:{key}", a.get("alt", ""))
            for item in (a.get("srcset") or a.get("data-srcset") or "").split(","):
                if item.strip():
                    self.add(item.strip().split()[0], f"{tag}:srcset", a.get("alt", ""))
        if tag == "meta" and (a.get("property") or a.get("name") or "").lower() in (
                "og:image", "og:image:url", "twitter:image", "og:video", "og:video:url"):
            self.add(a.get("content"), "meta")
        if tag == "a" and MEDIA.search(a.get("href") or ""):
            self.add(a.get("href"), "attachment-link", a.get("title", ""))


def inspect_page(args):
    public_url(args.url)
    if args.html:
        text = Path(args.html).read_text(encoding="utf-8")
    else:
        with urlopen(Request(args.url, headers=headers()), timeout=20) as r:
            text = r.read(12 * 1024 * 1024).decode("utf-8", "replace")
    parser = MediaLinks(args.url)
    parser.feed(text)
    decoded = html.unescape(text.replace("\\/", "/").replace("\\u002F", "/").replace("\\u0026", "&"))
    for value in re.findall(r'https?://[^\s<>"\x27\\]+', decoded):
        if MEDIA.search(value):
            parser.add(value, "embedded-json-or-css")
    items = list(parser.items.values())
    if args.match:
        items = [x for x in items if args.match.lower() in (x["url"] + x["label"]).lower()]
    result = {"page": args.url, "total": len(items), "candidates": items}
    if args.out:
        p = Path(args.out); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result if not args.out else {"out": str(p), "total": len(items), "preview": items[:8]}


def download(args):
    public_url(args.url)
    p = Path(args.out)
    if p.exists():
        raise FileExistsError(f"Keep the existing asset; select a new filename: {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    partial = p.with_name(p.name + ".part")
    if partial.exists():
        raise FileExistsError(f"A partial download already exists: {partial}")
    started, total = time.monotonic(), 0
    try:
        with urlopen(Request(args.url, headers=headers(args.referer)), timeout=20) as r, partial.open("xb") as f:
            mime = r.headers.get("Content-Type", "").lower()
            if "text/html" in mime:
                raise ValueError("Received an HTML page, not a media file")
            while chunk := r.read(256 * 1024):
                total += len(chunk)
                if total > args.max_mb * 1024 * 1024 or time.monotonic() - started > 120:
                    raise ValueError("Download limit reached; use a smaller clip or an explicit larger size limit")
                f.write(chunk)
        # CDNs sometimes serve valid images as application/octet-stream.
        info = probe(partial)
        partial.rename(p)
        return {"path": str(p), "bytes": total, **info}
    except Exception:
        if partial.exists():
            partial.unlink()
        raise


def ffmpeg_output(args, frame=False):
    p = Path(args.out)
    if p.exists():
        raise FileExistsError(f"Select a new output filename: {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n"]
    if args.input.startswith(("http://", "https://")):
        cmd += ["-rw_timeout", "15000000", "-user_agent", UA]
        if args.referer:
            cmd += ["-referer", args.referer]
    cmd += ["-ss", str(args.start), "-i", args.input]
    if frame:
        cmd += ["-frames:v", "1", "-update", "1", str(p)]
    else:
        cmd += ["-t", str(args.duration), "-map", "0:v:0", "-map", "0:a:0?",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-movflags", "+faststart", str(p)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60, check=True)
        return {"path": str(p), **probe(p)}
    except Exception:
        if p.exists():
            p.unlink()
        raise


def bilibili_clip(args):
    """Use the optional maintained platform adapter; never equate advertised and available quality."""
    from bilibili_api import video
    match = re.search(r"BV[0-9A-Za-z]{10}", args.url)
    if not match:
        raise ValueError("Use a BVID or canonical Bilibili video URL")
    bvid = match.group(0)
    out = Path(args.out)
    if out.exists():
        raise FileExistsError(f"Select a new output filename: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    async def resolve():
        return await asyncio.wait_for(video.Video(bvid=bvid).get_download_url(args.page - 1), timeout=25)
    data = asyncio.run(resolve())
    dash = data.get("dash", {})
    choices = [v for v in dash.get("video", []) if v.get("height", 0) <= args.height]
    if not choices or not dash.get("audio"):
        raise ValueError("No available DASH video/audio pair in this session; inspect the platform response")
    selected = max(choices, key=lambda v: (v.get("height", 0), v.get("codecs", "").startswith("avc1")))
    audio = max(dash["audio"], key=lambda a: a.get("bandwidth", 0))
    referer = f"https://www.bilibili.com/video/{bvid}"
    cache = Path(args.cache_dir) if args.cache_dir else out.parent / "sources"
    cache.mkdir(parents=True, exist_ok=True)
    files = []
    for role, item in (("video", selected), ("audio", audio)):
        # Include the actual stream id/codec to avoid confusing different representations.
        codec = re.sub(r"[^a-z0-9]", "", item.get("codecs", "unknown"))
        p = cache / f"{bvid}-p{args.page}-{role}-{item.get('id', 0)}-{codec}.mp4"
        if not p.exists():
            u = item.get("baseUrl") or item.get("base_url")
            partial = p.with_name(p.name + ".part")
            if partial.exists():
                raise FileExistsError(f"Keep the unfinished source download and inspect it first: {partial}")
            try:
                total = 0
                started = time.monotonic()
                print(f"Downloading {bvid} page {args.page} {role} stream", file=sys.stderr, flush=True)
                with urlopen(Request(u, headers=headers(referer)), timeout=20) as r, partial.open("xb") as f:
                    while chunk := r.read(256 * 1024):
                        total += len(chunk)
                        if total > args.max_mb * 1024 * 1024 or time.monotonic() - started > 120:
                            raise ValueError("Source stream exceeds the configured size or time limit")
                        f.write(chunk)
                partial.rename(p)
            except Exception:
                if partial.exists():
                    partial.unlink()
                raise
        files.append(p)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
           "-ss", str(args.start), "-i", str(files[0]), "-ss", str(args.start), "-i", str(files[1]),
           "-t", str(args.duration), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
           "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(out)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=60, check=True)
        return {"path": str(out), "source": referer, "page": args.page,
                "available_height": selected.get("height"), **probe(out)}
    except Exception:
        if out.exists():
            out.unlink()
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest="op", required=True)
    a = subs.add_parser("inspect", help="Find image/video/manifest candidates in public HTML")
    a.add_argument("url"); a.add_argument("--html"); a.add_argument("--match"); a.add_argument("--out")
    a = subs.add_parser("download", help="Download one original asset and report real dimensions/tracks")
    a.add_argument("url"); a.add_argument("--out", required=True); a.add_argument("--referer")
    a.add_argument("--max-mb", type=int, default=80)
    for name in ("clip", "frame"):
        a = subs.add_parser(name)
        a.add_argument("input"); a.add_argument("--out", required=True)
        a.add_argument("--start", type=float, default=0); a.add_argument("--referer")
        if name == "clip":
            a.add_argument("--duration", type=float, required=True)
    a = subs.add_parser("probe"); a.add_argument("input")
    a = subs.add_parser("bilibili", help="Resolve available platform DASH streams, cache, merge and cut")
    a.add_argument("url"); a.add_argument("--out", required=True)
    a.add_argument("--start", type=float, default=0); a.add_argument("--duration", type=float, required=True)
    a.add_argument("--page", type=int, default=1); a.add_argument("--height", type=int, default=1080)
    a.add_argument("--cache-dir"); a.add_argument("--max-mb", type=int, default=150)
    args = ap.parse_args()
    if args.op == "bilibili" and (args.page < 1 or args.height < 1):
        ap.error("Page and requested height must be positive")
    if getattr(args, "start", 0) < 0 or getattr(args, "duration", 1) <= 0:
        ap.error("Start must be nonnegative and duration must be positive")
    try:
        result = bilibili_clip(args) if args.op == "bilibili" else inspect_page(args) if args.op == "inspect" else download(args) if args.op == "download" else (
            probe(args.input) if args.op == "probe" else ffmpeg_output(args, args.op == "frame"))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        # Do not print subprocess commands containing signed CDN URLs or cookies.
        detail = f"external tool exited {e.returncode}" if isinstance(e, subprocess.CalledProcessError) else str(e)
        print(json.dumps({"error": type(e).__name__, "detail": detail}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
