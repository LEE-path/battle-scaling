"""Bounded local extraction; offsets always refer to the resulting UTF-8 text.

The extraction design follows battle-scaling's offline novel_evidence reader;
chapter/chunk organisation follows novel-refpack. No supplied text is executed.
"""
from html.parser import HTMLParser
import io
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET
import zipfile

MAX_FILE = 64 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024
MAX_MEMBER = 32 * 1024 * 1024


def read_bounded(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError("Source must be a regular file of at most 64 MiB")
    data = path.read_bytes()
    if len(data) > MAX_FILE:
        raise ValueError("Source exceeds size limit")
    return data


def _xml(data):
    if b"<!ENTITY" in data.upper() or b"<!DOCTYPE" in data.upper():
        raise ValueError("XML entity and DOCTYPE declarations are unsupported")
    return ET.fromstring(data)


def _tag(tag):
    return tag.rsplit("}", 1)[-1]


def _member(name):
    if not isinstance(name, str) or "\\" in name or ":" in name:
        raise ValueError("Unsafe archive member")
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("Unsafe archive member traversal")
    return str(p)


class HtmlText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.buffer, self.hidden = [], [], 0

    def flush(self):
        text = "".join(self.buffer).strip()
        if text:
            self.lines.append(text)
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif not self.hidden and tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br"):
            self.flush()

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.buffer.append(data)


def extract(path, data, encoding=None):
    ext = Path(path).suffix.lower()
    if ext in (".txt", ".md"):
        enc = encoding or ("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        try:
            text = data.decode(enc)
        except (UnicodeError, LookupError) as exc:
            raise ValueError("Text decoding failed; supply --encoding explicitly") from exc
        # Newline conversion is explicit and happens before any coordinates exist.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text, [{"line_start": 1, "line_end": text.count("\n") + 1,
                       "member": Path(path).name}], enc
    if ext not in (".epub", ".docx"):
        raise ValueError("Supported sources: TXT, MD, EPUB, DOCX")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid EPUB/DOCX archive") from exc
    with archive as z:
        entries = z.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > MAX_EXPANDED:
            raise ValueError("Archive exceeds expanded size limit")
        names = set()
        for entry in entries:
            _member(entry.filename)
            if entry.filename in names or entry.file_size > MAX_MEMBER:
                raise ValueError("Duplicate or oversized archive member")
            names.add(entry.filename)

        def get(name):
            name = _member(name)
            if name not in names:
                raise ValueError("Required archive member missing: " + name)
            return z.read(name)

        lines, locators = [], []
        if ext == ".docx":
            doc = _xml(get("word/document.xml"))
            for n, p in enumerate((x for x in doc.iter() if _tag(x.tag) == "p"), 1):
                parts = []
                for node in p.iter():
                    tag = _tag(node.tag)
                    if tag == "t":
                        parts.append(node.text or "")
                    elif tag == "tab":
                        parts.append("\t")
                    elif tag in ("br", "cr"):
                        parts.append("\n")
                start = len(lines) + 1
                lines.extend("".join(parts).split("\n"))
                locators.append({"line_start": start, "line_end": len(lines),
                                 "member": "word/document.xml", "paragraph": n})
        else:
            container = _xml(get("META-INF/container.xml"))
            rootfile = next((x.attrib.get("full-path") for x in container.iter()
                             if _tag(x.tag) == "rootfile"), None)
            if not rootfile:
                raise ValueError("EPUB container has no rootfile")
            rootfile = _member(rootfile)
            opf, parent = _xml(get(rootfile)), PurePosixPath(rootfile).parent
            items = {x.attrib.get("id"): x.attrib.get("href") for x in opf.iter() if _tag(x.tag) == "item"}
            refs = [x.attrib.get("idref") for x in opf.iter() if _tag(x.tag) == "itemref"]
            if not refs:
                raise ValueError("EPUB spine is empty")
            for n, ref in enumerate(refs, 1):
                href = items.get(ref)
                if not href:
                    raise ValueError("Unknown EPUB spine member")
                member = _member(str(parent / href.split("#", 1)[0]))
                parser = HtmlText()
                parser.feed(get(member).decode("utf-8-sig", errors="strict"))
                parser.flush()
                for paragraph, line in enumerate(parser.lines, 1):
                    lines.append(line)
                    locators.append({"line_start": len(lines), "line_end": len(lines),
                                     "member": member, "spine_index": n, "paragraph": paragraph})
        text = "\n".join(lines) + ("\n" if lines else "")
        return text, locators, "zip_xml_utf8_extraction"
