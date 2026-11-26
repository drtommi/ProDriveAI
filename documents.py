"""Local document worker. Only bounded excerpts or search hits leave this process."""
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile


def docx_text(path):
    from lxml import etree
    with ZipFile(path) as archive:
        info = archive.getinfo("word/document.xml")
        if info.file_size > 32 * 1024 * 1024:
            raise ValueError("The expanded DOCX body exceeds 32 MiB.")
        with archive.open(info) as entry:
            root = etree.parse(entry, etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True))
    if root.docinfo.doctype:
        raise ValueError("DOCX with XML document types is unsupported.")
    ns = etree.QName(root.getroot()).namespace
    values = {"p": "\n", "tab": "\t", "br": "\n", "cr": "\n"}
    pieces = []
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        tag = etree.QName(element)
        if tag.namespace == ns:
            if tag.localname == "t":
                pieces.append(element.text or "")
            elif tag.localname in values:
                pieces.append(values[tag.localname])
    return "".join(pieces).lstrip("\n")


def pdf_text(page):
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_bounded().replace("\r\n", "\n")
    finally:
        textpage.close()
    if text.strip():
        return text, "text"
    if not shutil.which("tesseract"):
        raise ValueError("Page has no embedded text. Install Tesseract on the host for OCR.")
    width, height = page.get_size()
    if min(width, height) <= 0:
        raise ValueError("Invalid PDF page dimensions.")
    scale = min(2.5, 3600 / max(width, height), math.sqrt(8_000_000 / (width * height)))
    bitmap = page.render(scale=scale)
    try:
        data = io.BytesIO()
        bitmap.to_pil().save(data, format="PNG")
    finally:
        bitmap.close()
    result = subprocess.run(["tesseract", "stdin", "stdout", "-l", os.getenv("PRODRIVEAI_OCR_LANG", "eng")],
                            input=data.getvalue(), capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError("OCR failed. Check the installed Tesseract language data.")
    return result.stdout.decode("utf-8"), "ocr"


def process(path, options):
    search = "query" in options
    hits, skipped = [], []
    if search:
        pattern = re.compile(re.escape(options["query"]), re.IGNORECASE)
    pdf = None
    if path.suffix.lower() == ".pdf":
        import pypdfium2
        pdf = pypdfium2.PdfDocument(path)
    try:
        pages = len(pdf) if pdf is not None else 1
        first = options.get("page", 1)
        if not 1 <= first <= pages:
            raise ValueError("Page outside the document.")
        last = pages if search else first
        for number in range(first, last + 1):
            try:
                if pdf is not None:
                    page = pdf[number - 1]
                    try:
                        text, method = pdf_text(page)
                    finally:
                        page.close()
                elif path.suffix.lower() == ".docx":
                    text, method = docx_text(path), "text"
                else:
                    text, method = path.read_text(encoding="utf-8-sig"), "text"
            except (ValueError, subprocess.TimeoutExpired) as error:
                if not search:
                    raise
                if len(skipped) < 10:
                    skipped.append({"page": number, "reason": str(error)[:160]})
                continue
            if not search:
                offset = options["offset"]
                if offset > len(text):
                    raise ValueError("Offset outside the extracted page.")
                end = min(offset + options["maxChars"], len(text))
                return {"page": number, "pages": pages, "method": method, "text": text[offset:end],
                        "next": {"page": number, "offset": end} if end < len(text) else
                                ({"page": number + 1, "offset": 0} if number < pages else None)}
            for match in pattern.finditer(text):
                hits.append({"page": number, "offset": match.start(), "method": method,
                             "snippet": text[max(0, match.start()-100):match.end()+160]})
                if len(hits) == 3:
                    return {"matches": hits, "hitLimitReached": True, "skippedPages": skipped}
        return {"matches": hits, "hitLimitReached": False, "skippedPages": skipped}
    finally:
        if pdf is not None:
            pdf.close()


try:
    result = process(Path(sys.argv[1]), json.load(sys.stdin))
except ImportError:
    result = {"error": "Install the ProDriveAI document requirements in PRODRIVEAI_PYTHON."}
except (ValueError, subprocess.TimeoutExpired) as exc:
    result = {"error": str(exc)[:160]}
except Exception:
    result = {"error": "Cannot extract this document. It may be encrypted, corrupt, or unsupported."}
print(json.dumps(result))
